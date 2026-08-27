module u19_high_add_select #(
    parameter W = 22
) (
    input wire [W-1:0] accum_in,
    input wire [W-1:0] mcand_in,
    input wire mult_lsb,
    output wire [W-1:0] add_term,
    output wire [W-1:0] accum_out,
    output wire [W-1:0] accum_alias
);
    wire [W-1:0] local_sum;

    assign add_term = mult_lsb ? mcand_in : {W{1'b0}};
    assign local_sum = accum_in + add_term;
    assign accum_out = local_sum;
    assign accum_alias = accum_out;
endmodule

module u19_high_shift_left #(
    parameter W = 22
) (
    input wire [W-1:0] mcand_in,
    output wire [W-1:0] mcand_out,
    output wire [W-1:0] mcand_alias
);
    assign mcand_out = mcand_in << 1;
    assign mcand_alias = mcand_out;
endmodule

module u19_high_shift_right #(
    parameter W = 11
) (
    input wire [W-1:0] mult_in,
    output wire [W-1:0] mult_out,
    output wire [W-1:0] mult_alias
);
    assign mult_out = mult_in >> 1;
    assign mult_alias = mult_out;
endmodule

module u19_high_step_pack #(
    parameter W = 11,
    parameter PRODUCT_W = 22
) (
    input wire [PRODUCT_W-1:0] accum_in,
    input wire [PRODUCT_W-1:0] mcand_in,
    input wire [W-1:0] mult_in,
    input wire mult_lsb,
    output wire [PRODUCT_W-1:0] add_term,
    output wire [PRODUCT_W-1:0] next_accum,
    output wire [PRODUCT_W-1:0] next_accum_alias,
    output wire [PRODUCT_W-1:0] next_mcand,
    output wire [PRODUCT_W-1:0] next_mcand_alias,
    output wire [W-1:0] next_mult,
    output wire [W-1:0] next_mult_alias
);
    u19_high_add_select #(.W(PRODUCT_W)) u_add (
        .accum_in(accum_in),
        .mcand_in(mcand_in),
        .mult_lsb(mult_lsb),
        .add_term(add_term),
        .accum_out(next_accum),
        .accum_alias(next_accum_alias)
    );

    u19_high_shift_left #(.W(PRODUCT_W)) u_shift_left (
        .mcand_in(mcand_in),
        .mcand_out(next_mcand),
        .mcand_alias(next_mcand_alias)
    );

    u19_high_shift_right #(.W(W)) u_shift_right (
        .mult_in(mult_in),
        .mult_out(next_mult),
        .mult_alias(next_mult_alias)
    );
endmodule

module serial_multiplier_11_PPA_Kogge_Stone #(
    parameter width = 11
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

    wire do_start;
    wire do_step;
    wire last_step;
    wire [PRODUCT_W-1:0] start_mcand;

    wire [PRODUCT_W-1:0] accum_alias0;
    wire [PRODUCT_W-1:0] mcand_alias0;
    wire [width-1:0] mult_alias0;

    wire [PRODUCT_W-1:0] add_term;
    wire [PRODUCT_W-1:0] next_accum;
    wire [PRODUCT_W-1:0] next_accum_alias;
    wire [PRODUCT_W-1:0] next_mcand;
    wire [PRODUCT_W-1:0] next_mcand_alias;
    wire [width-1:0] next_mult;
    wire [width-1:0] next_mult_alias;

    wire [width-1:0] mult_tap_bus;
    wire [PRODUCT_W-1:0] accum_shadow_bus;
    wire [PRODUCT_W-1:0] mcand_shadow_bus;

    assign do_start = en && !busy;
    assign do_step = busy;
    assign last_step = (step_count == width - 1);
    assign start_mcand = {{width{1'b0}}, A[width:1]};

    assign accum_alias0 = accum_reg;
    assign mcand_alias0 = mcand_reg;
    assign mult_alias0 = mult_reg;

    generate
        genvar i;
        for (i = 0; i < width; i = i + 1) begin : gen_mult_taps
            assign mult_tap_bus[i] = mult_alias0[i];
        end
    endgenerate

    generate
        genvar j;
        for (j = 0; j < PRODUCT_W; j = j + 1) begin : gen_accum_shadow
            assign accum_shadow_bus[j] = accum_alias0[j];
            assign mcand_shadow_bus[j] = mcand_alias0[j];
        end
    endgenerate

    u19_high_step_pack #(.W(width), .PRODUCT_W(PRODUCT_W)) u_step_pack (
        .accum_in(accum_shadow_bus),
        .mcand_in(mcand_shadow_bus),
        .mult_in(mult_tap_bus),
        .mult_lsb(mult_tap_bus[0]),
        .add_term(add_term),
        .next_accum(next_accum),
        .next_accum_alias(next_accum_alias),
        .next_mcand(next_mcand),
        .next_mcand_alias(next_mcand_alias),
        .next_mult(next_mult),
        .next_mult_alias(next_mult_alias)
    );

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
            if (do_start) begin
                busy <= 1'b1;
                accum_reg <= {PRODUCT_W{1'b0}};
                mcand_reg <= start_mcand;
                mult_reg <= B[width:1];
                step_count <= 8'd0;
            end else if (do_step) begin
                accum_reg <= next_accum_alias;
                mcand_reg <= next_mcand_alias;
                mult_reg <= next_mult_alias;
                if (last_step) begin
                    busy <= 1'b0;
                    valid <= 1'b1;
                    S <= next_accum_alias;
                end
                step_count <= step_count + 8'd1;
            end
        end
    end
endmodule
