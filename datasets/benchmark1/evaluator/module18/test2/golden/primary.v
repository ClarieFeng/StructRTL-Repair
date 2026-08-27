module u18_partial_pair #(
    parameter W = 9,
    parameter SHIFT0 = 0,
    parameter SHIFT1 = 1
) (
    input wire signed [W-1:0] a_s,
    input wire bit0_en,
    input wire bit1_en,
    output wire signed [(W*2)-1:0] pair_sum
);
    wire signed [(W*2)-1:0] a_ext;
    wire signed [(W*2)-1:0] partial0;
    wire signed [(W*2)-1:0] partial1;

    assign a_ext = {{W{a_s[W-1]}}, a_s};
    assign partial0 = bit0_en ? (a_ext <<< SHIFT0) : {(W*2){1'b0}};
    assign partial1 = bit1_en ? (a_ext <<< SHIFT1) : {(W*2){1'b0}};
    assign pair_sum = partial0 + partial1;
endmodule

module u18_signed_tail #(
    parameter W = 9,
    parameter POS_SHIFT = 6,
    parameter NEG_SHIFT = 8
) (
    input wire signed [W-1:0] a_s,
    input wire pos_en,
    input wire neg_en,
    output wire signed [(W*2)-1:0] tail_sum
);
    wire signed [(W*2)-1:0] a_ext;
    wire signed [(W*2)-1:0] pos_partial;
    wire signed [(W*2)-1:0] neg_partial;

    assign a_ext = {{W{a_s[W-1]}}, a_s};
    assign pos_partial = pos_en ? (a_ext <<< POS_SHIFT) : {(W*2){1'b0}};
    assign neg_partial = neg_en ? -(a_ext <<< NEG_SHIFT) : {(W*2){1'b0}};
    assign tail_sum = pos_partial + neg_partial;
endmodule

module signed_parallel_multiplier_9_PPA_Kogge_Stone #(
    parameter width = 9
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    output wire [width*2-1:0] S
);
    wire signed [width-1:0] a_s;
    wire signed [width-1:0] b_s;

    wire signed [(width*2)-1:0] stage0_pair0;
    wire signed [(width*2)-1:0] stage0_pair1;
    wire signed [(width*2)-1:0] stage0_pair2;
    wire signed [(width*2)-1:0] stage0_pair3;
    wire signed [(width*2)-1:0] stage0_tail;

    wire signed [(width*2)-1:0] stage0_alias0;
    wire signed [(width*2)-1:0] stage0_alias1;
    wire signed [(width*2)-1:0] stage0_alias2;
    wire signed [(width*2)-1:0] stage0_alias3;
    wire signed [(width*2)-1:0] stage0_alias4;

    wire signed [(width*2)-1:0] stage1_sum0;
    wire signed [(width*2)-1:0] stage1_sum1;
    wire signed [(width*2)-1:0] stage1_sum2;
    wire signed [(width*2)-1:0] stage1_alias0;
    wire signed [(width*2)-1:0] stage1_alias1;
    wire signed [(width*2)-1:0] stage1_alias2;

    wire signed [(width*2)-1:0] stage2_sum0;
    wire signed [(width*2)-1:0] stage2_sum1;
    wire signed [(width*2)-1:0] stage2_alias0;
    wire signed [(width*2)-1:0] stage2_alias1;
    wire signed [(width*2)-1:0] final_product;

    assign a_s = A;
    assign b_s = B;

    u18_partial_pair #(.W(width), .SHIFT0(0), .SHIFT1(1)) u_pair0 (
        .a_s(a_s),
        .bit0_en(b_s[0]),
        .bit1_en(b_s[1]),
        .pair_sum(stage0_pair0)
    );

    u18_partial_pair #(.W(width), .SHIFT0(2), .SHIFT1(3)) u_pair1 (
        .a_s(a_s),
        .bit0_en(b_s[2]),
        .bit1_en(b_s[3]),
        .pair_sum(stage0_pair1)
    );

    u18_partial_pair #(.W(width), .SHIFT0(4), .SHIFT1(5)) u_pair2 (
        .a_s(a_s),
        .bit0_en(b_s[4]),
        .bit1_en(b_s[5]),
        .pair_sum(stage0_pair2)
    );

    u18_partial_pair #(.W(width), .SHIFT0(6), .SHIFT1(7)) u_pair3 (
        .a_s(a_s),
        .bit0_en(b_s[6]),
        .bit1_en(b_s[7]),
        .pair_sum(stage0_pair3)
    );

    u18_signed_tail #(.W(width), .POS_SHIFT(0), .NEG_SHIFT(8)) u_tail (
        .a_s(a_s),
        .pos_en(1'b0),
        .neg_en(b_s[8]),
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
