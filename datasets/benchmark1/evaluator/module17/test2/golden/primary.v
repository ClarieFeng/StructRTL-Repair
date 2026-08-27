module u17_partial_pair #(
    parameter W = 11,
    parameter SHIFT0 = 0,
    parameter SHIFT1 = 1
) (
    input wire [W-1:0] a_u,
    input wire bit0_en,
    input wire bit1_en,
    output wire [(W*2)-1:0] pair_sum
);
    wire [(W*2)-1:0] a_ext;
    wire [(W*2)-1:0] partial0;
    wire [(W*2)-1:0] partial1;

    assign a_ext = {{W{1'b0}}, a_u};
    assign partial0 = bit0_en ? (a_ext << SHIFT0) : {(W*2){1'b0}};
    assign partial1 = bit1_en ? (a_ext << SHIFT1) : {(W*2){1'b0}};
    assign pair_sum = partial0 + partial1;
endmodule

module u17_partial_tail #(
    parameter W = 11,
    parameter SHIFT0 = 8,
    parameter SHIFT1 = 9,
    parameter SHIFT2 = 10
) (
    input wire [W-1:0] a_u,
    input wire bit0_en,
    input wire bit1_en,
    input wire bit2_en,
    output wire [(W*2)-1:0] tail_sum
);
    wire [(W*2)-1:0] a_ext;
    wire [(W*2)-1:0] partial0;
    wire [(W*2)-1:0] partial1;
    wire [(W*2)-1:0] partial2;

    assign a_ext = {{W{1'b0}}, a_u};
    assign partial0 = bit0_en ? (a_ext << SHIFT0) : {(W*2){1'b0}};
    assign partial1 = bit1_en ? (a_ext << SHIFT1) : {(W*2){1'b0}};
    assign partial2 = bit2_en ? (a_ext << SHIFT2) : {(W*2){1'b0}};
    assign tail_sum = partial0 + partial1 + partial2;
endmodule

module parallel_multiplier_11_PPA_Kogge_Stone #(
    parameter width = 11
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    output wire [width*2-1:0] S
);
    wire [width-1:0] a_u;
    wire [width-1:0] b_u;

    wire [(width*2)-1:0] stage0_pair0;
    wire [(width*2)-1:0] stage0_pair1;
    wire [(width*2)-1:0] stage0_pair2;
    wire [(width*2)-1:0] stage0_pair3;
    wire [(width*2)-1:0] stage0_tail;

    wire [(width*2)-1:0] stage0_alias0;
    wire [(width*2)-1:0] stage0_alias1;
    wire [(width*2)-1:0] stage0_alias2;
    wire [(width*2)-1:0] stage0_alias3;
    wire [(width*2)-1:0] stage0_alias4;

    wire [(width*2)-1:0] stage1_sum0;
    wire [(width*2)-1:0] stage1_sum1;
    wire [(width*2)-1:0] stage1_sum2;
    wire [(width*2)-1:0] stage1_alias0;
    wire [(width*2)-1:0] stage1_alias1;
    wire [(width*2)-1:0] stage1_alias2;

    wire [(width*2)-1:0] stage2_sum0;
    wire [(width*2)-1:0] stage2_sum1;
    wire [(width*2)-1:0] stage2_alias0;
    wire [(width*2)-1:0] stage2_alias1;
    wire [(width*2)-1:0] final_product;

    assign a_u = A;
    assign b_u = B;

    u17_partial_pair #(.W(width), .SHIFT0(0), .SHIFT1(1)) u_pair0 (
        .a_u(a_u),
        .bit0_en(b_u[0]),
        .bit1_en(b_u[1]),
        .pair_sum(stage0_pair0)
    );

    u17_partial_pair #(.W(width), .SHIFT0(2), .SHIFT1(3)) u_pair1 (
        .a_u(a_u),
        .bit0_en(b_u[2]),
        .bit1_en(b_u[3]),
        .pair_sum(stage0_pair1)
    );

    u17_partial_pair #(.W(width), .SHIFT0(4), .SHIFT1(5)) u_pair2 (
        .a_u(a_u),
        .bit0_en(b_u[4]),
        .bit1_en(b_u[5]),
        .pair_sum(stage0_pair2)
    );

    u17_partial_pair #(.W(width), .SHIFT0(6), .SHIFT1(7)) u_pair3 (
        .a_u(a_u),
        .bit0_en(b_u[6]),
        .bit1_en(b_u[7]),
        .pair_sum(stage0_pair3)
    );

    u17_partial_tail #(.W(width), .SHIFT0(8), .SHIFT1(9), .SHIFT2(10)) u_tail (
        .a_u(a_u),
        .bit0_en(b_u[8]),
        .bit1_en(b_u[9]),
        .bit2_en(b_u[10]),
        .tail_sum(stage0_tail)
    );

    assign stage0_alias0 = stage0_pair0;
    assign stage0_alias1 = stage0_pair1;
    assign stage0_alias2 = stage0_pair2;
    assign stage0_alias3 = stage0_pair3;
    assign stage0_alias4 = stage0_tail;

    assign stage1_sum0 = stage0_alias0 + stage0_alias1;
    assign stage1_sum1 = stage0_alias2 + stage0_alias3;
    assign stage1_sum2 = stage0_alias4;

    assign stage1_alias0 = stage1_sum0;
    assign stage1_alias1 = stage1_sum1;
    assign stage1_alias2 = stage1_sum2;

    assign stage2_sum0 = stage1_alias0 + stage1_alias1;
    assign stage2_sum1 = stage1_alias2;
    assign stage2_alias0 = stage2_sum0;
    assign stage2_alias1 = stage2_sum1;

    assign final_product = stage2_alias0 + stage2_alias1;
    assign S = final_product;
endmodule
