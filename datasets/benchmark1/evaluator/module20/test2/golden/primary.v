module u20_medium_sign_prep #(
    parameter W = 11
) (
    input wire [W:1] a_in,
    input wire [W:1] b_in,
    output wire sign_out,
    output wire [W-1:0] abs_a,
    output wire [W-1:0] abs_b
);
    assign sign_out = a_in[W] ^ b_in[W];
    assign abs_a = a_in[W] ? (~a_in[W:1] + 1'b1) : a_in[W:1];
    assign abs_b = b_in[W] ? (~b_in[W:1] + 1'b1) : b_in[W:1];
endmodule

module u20_medium_add_mux #(
    parameter W = 22
) (
    input wire [W-1:0] accum_in,
    input wire [W-1:0] mcand_in,
    input wire mult_lsb,
    output wire [W-1:0] add_term,
    output wire [W-1:0] accum_out
);
    assign add_term = mult_lsb ? mcand_in : {W{1'b0}};
    assign accum_out = accum_in + add_term;
endmodule

module u20_medium_shift_pack #(
    parameter W = 11,
    parameter PRODUCT_W = 22
) (
    input wire [PRODUCT_W-1:0] mcand_in,
    input wire [W-1:0] mult_in,
    output wire [PRODUCT_W-1:0] mcand_out,
    output wire [W-1:0] mult_out
);
    assign mcand_out = mcand_in << 1;
    assign mult_out = mult_in >> 1;
endmodule

module signed_serial_multiplier_11_C_Sel_A #(
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
    reg sign_reg;
    reg [PRODUCT_W-1:0] accum_reg;
    reg [PRODUCT_W-1:0] mcand_reg;
    reg [width-1:0] mult_reg;
    reg [7:0] step_count;

    wire do_start;
    wire do_step;
    wire last_step;

    wire prep_sign;
    wire [width-1:0] prep_abs_a;
    wire [width-1:0] prep_abs_b;
    wire [PRODUCT_W-1:0] start_mcand;

    wire [PRODUCT_W-1:0] add_term;
    wire [PRODUCT_W-1:0] next_accum_unsigned;
    wire [PRODUCT_W-1:0] next_mcand;
    wire [width-1:0] next_mult;
    wire [PRODUCT_W-1:0] final_unsigned;
    wire [PRODUCT_W-1:0] final_signed;

    wire [PRODUCT_W-1:0] accum_alias0;
    wire [PRODUCT_W-1:0] accum_alias1;
    wire [PRODUCT_W-1:0] mcand_alias0;
    wire [PRODUCT_W-1:0] mcand_alias1;
    wire [width-1:0] mult_alias0;
    wire [width-1:0] mult_alias1;

    assign do_start = en && !busy;
    assign do_step = busy;
    assign last_step = (step_count == width - 1);
    assign start_mcand = {{width{1'b0}}, prep_abs_a};

    u20_medium_sign_prep #(.W(width)) u_sign_prep (
        .a_in(A),
        .b_in(B),
        .sign_out(prep_sign),
        .abs_a(prep_abs_a),
        .abs_b(prep_abs_b)
    );

    assign accum_alias0 = accum_reg;
    assign mcand_alias0 = mcand_reg;
    assign mult_alias0 = mult_reg;

    u20_medium_add_mux #(.W(PRODUCT_W)) u_add_mux (
        .accum_in(accum_alias0),
        .mcand_in(mcand_alias0),
        .mult_lsb(mult_alias0[0]),
        .add_term(add_term),
        .accum_out(next_accum_unsigned)
    );

    u20_medium_shift_pack #(.W(width), .PRODUCT_W(PRODUCT_W)) u_shift_pack (
        .mcand_in(mcand_alias0),
        .mult_in(mult_alias0),
        .mcand_out(next_mcand),
        .mult_out(next_mult)
    );

    assign accum_alias1 = next_accum_unsigned;
    assign mcand_alias1 = next_mcand;
    assign mult_alias1 = next_mult;
    assign final_unsigned = accum_alias1;
    assign final_signed = sign_reg ? (~final_unsigned + 1'b1) : final_unsigned;

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
            if (do_start) begin
                busy <= 1'b1;
                sign_reg <= prep_sign;
                accum_reg <= {PRODUCT_W{1'b0}};
                mcand_reg <= start_mcand;
                mult_reg <= prep_abs_b;
                step_count <= 8'd0;
            end else if (do_step) begin
                accum_reg <= accum_alias1;
                mcand_reg <= mcand_alias1;
                mult_reg <= mult_alias1;
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
