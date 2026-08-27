module serial_multiplier_7_C_Skip_A #(
    parameter width = 7
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
    reg [PRODUCT_W-1:0] accum_reg;
    reg [PRODUCT_W-1:0] mcand_reg;
    reg [width-1:0] mult_reg;
    reg [7:0] step_count;

    wire [PRODUCT_W-1:0] start_mcand;
    wire [PRODUCT_W-1:0] add_term;
    wire [PRODUCT_W-1:0] next_accum;
    wire [PRODUCT_W-1:0] next_mcand;
    wire [width-1:0] next_mult;
    wire last_step;

    assign start_mcand = {{width{1'b0}}, A[width:1]};
    assign add_term = mult_reg[0] ? mcand_reg : {PRODUCT_W{1'b0}};
    assign next_accum = accum_reg + add_term;
    assign next_mcand = mcand_reg << 1;
    assign next_mult = mult_reg >> 1;
    assign last_step = (step_count == width - 1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid <= 1'b0;
            S <= {PRODUCT_W{1'b0}};
            busy <= 1'b0;
            accum_reg <= {PRODUCT_W{1'b0}};
            mcand_reg <= {PRODUCT_W{1'b0}};
            mult_reg <= {width{1'b0}};
            step_count <= 8'd0;
        end else begin
            valid <= 1'b0;
            if (en && !busy) begin
                busy <= 1'b1;
                accum_reg <= {PRODUCT_W{1'b0}};
                mcand_reg <= start_mcand;
                mult_reg <= B[width:1];
                step_count <= 8'd0;
            end else if (busy) begin
                accum_reg <= next_accum;
                mcand_reg <= next_mcand;
                mult_reg <= next_mult;
                if (last_step) begin
                    busy <= 1'b0;
                    valid <= 1'b1;
                    S <= next_accum;
                end
                step_count <= step_count + 8'd1;
            end
        end
    end
endmodule
