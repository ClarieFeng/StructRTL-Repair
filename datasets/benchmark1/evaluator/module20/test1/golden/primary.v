module signed_serial_multiplier_10_FA #(
    parameter width = 10
) (
    input wire clk,
    input wire rst_n,
    input wire en,
    input wire [width:1] A,
    input wire [width:1] B,
    output reg valid,
    output reg [width*2:1] S
);
    localparam PRODUCT_W = width * 2;

    reg busy;
    reg sign_reg;
    reg [PRODUCT_W-1:0] accum_reg;
    reg [PRODUCT_W-1:0] mcand_reg;
    reg [width-1:0] mult_reg;
    reg [7:0] step_count;

    wire sign_start;
    wire [width-1:0] abs_a;
    wire [width-1:0] abs_b;
    wire [PRODUCT_W-1:0] start_mcand;
    wire [PRODUCT_W-1:0] add_term;
    wire [PRODUCT_W-1:0] next_accum_unsigned;
    wire [PRODUCT_W-1:0] next_mcand;
    wire [width-1:0] next_mult;
    wire [PRODUCT_W-1:0] final_unsigned;
    wire [PRODUCT_W-1:0] final_signed;
    wire last_step;

    assign sign_start = A[width] ^ B[width];
    assign abs_a = A[width] ? (~A[width:1] + 1'b1) : A[width:1];
    assign abs_b = B[width] ? (~B[width:1] + 1'b1) : B[width:1];
    assign start_mcand = {{width{1'b0}}, abs_a};
    assign add_term = mult_reg[0] ? mcand_reg : {PRODUCT_W{1'b0}};
    assign next_accum_unsigned = accum_reg + add_term;
    assign next_mcand = mcand_reg << 1;
    assign next_mult = mult_reg >> 1;
    assign final_unsigned = next_accum_unsigned;
    assign final_signed = sign_reg ? (~final_unsigned + 1'b1) : final_unsigned;
    assign last_step = (step_count == width - 1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid <= 1'b0;
            S <= {PRODUCT_W{1'b0}};
            busy <= 1'b0;
            sign_reg <= 1'b0;
            accum_reg <= {PRODUCT_W{1'b0}};
            mcand_reg <= {PRODUCT_W{1'b0}};
            mult_reg <= {width{1'b0}};
            step_count <= 8'd0;
        end else begin
            valid <= 1'b0;
            if (en && !busy) begin
                busy <= 1'b1;
                sign_reg <= sign_start;
                accum_reg <= {PRODUCT_W{1'b0}};
                mcand_reg <= start_mcand;
                mult_reg <= abs_b;
                step_count <= 8'd0;
            end else if (busy) begin
                accum_reg <= next_accum_unsigned;
                mcand_reg <= next_mcand;
                mult_reg <= next_mult;
                if (last_step) begin
                    busy <= 1'b0;
                    valid <= 1'b1;
                    S <= final_signed;
                end
                step_count <= step_count + 8'd1;
            end
        end
    end
endmodule
