module u12_partial_pair #(
    parameter W = 12,
    parameter SHIFT0 = 0,
    parameter SHIFT1 = 1
) (
    input wire signed [W-1:0] a_s,
    input wire bit0_en,
    input wire bit1_en,
    output wire signed [(W*2)-1:0] pair_sum
);
    wire signed [(W*2)-1:0] a_ext = {{W{a_s[W-1]}}, a_s};
    wire signed [(W*2)-1:0] partial0 = bit0_en ? (a_ext <<< SHIFT0) : {(W*2){1'b0}};
    wire signed [(W*2)-1:0] partial1 = bit1_en ? (a_ext <<< SHIFT1) : {(W*2){1'b0}};

    assign pair_sum = partial0 + partial1;
endmodule

module u12_partial_tail #(
    parameter W = 12,
    parameter POS_SHIFT = 10,
    parameter NEG_SHIFT = 11
) (
    input wire signed [W-1:0] a_s,
    input wire pos_en,
    input wire neg_en,
    output wire signed [(W*2)-1:0] tail_sum
);
    wire signed [(W*2)-1:0] a_ext = {{W{a_s[W-1]}}, a_s};
    wire signed [(W*2)-1:0] pos_partial = pos_en ? (a_ext <<< POS_SHIFT) : {(W*2){1'b0}};
    wire signed [(W*2)-1:0] neg_partial = neg_en ? -(a_ext <<< NEG_SHIFT) : {(W*2){1'b0}};

    assign tail_sum = pos_partial + neg_partial;
endmodule

module Multi_Booth_signed_even #(
    parameter width = 12
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    wire signed [width-1:0] a_s = A[width:1];
    wire signed [width-1:0] b_s = B[width:1];

    wire signed [(width*2)-1:0] stage0_pair0;
    wire signed [(width*2)-1:0] stage0_pair1;
    wire signed [(width*2)-1:0] stage0_pair2;
    wire signed [(width*2)-1:0] stage0_pair3;
    wire signed [(width*2)-1:0] stage0_pair4;
    wire signed [(width*2)-1:0] stage0_tail;

    wire signed [(width*2)-1:0] stage1_sum0;
    wire signed [(width*2)-1:0] stage1_sum1;
    wire signed [(width*2)-1:0] stage1_sum2;

    wire signed [(width*2)-1:0] stage2_sum0;
    wire signed [(width*2)-1:0] stage2_sum1;
    wire signed [(width*2)-1:0] final_product;

    u12_partial_pair #(.W(width), .SHIFT0(0), .SHIFT1(1)) u_pair0 (
        .a_s(a_s),
        .bit0_en(b_s[0]),
        .bit1_en(b_s[1]),
        .pair_sum(stage0_pair0)
    );

    u12_partial_pair #(.W(width), .SHIFT0(2), .SHIFT1(3)) u_pair1 (
        .a_s(a_s),
        .bit0_en(b_s[2]),
        .bit1_en(b_s[3]),
        .pair_sum(stage0_pair1)
    );

    u12_partial_pair #(.W(width), .SHIFT0(4), .SHIFT1(5)) u_pair2 (
        .a_s(a_s),
        .bit0_en(b_s[4]),
        .bit1_en(b_s[5]),
        .pair_sum(stage0_pair2)
    );

    u12_partial_pair #(.W(width), .SHIFT0(6), .SHIFT1(7)) u_pair3 (
        .a_s(a_s),
        .bit0_en(b_s[6]),
        .bit1_en(b_s[7]),
        .pair_sum(stage0_pair3)
    );

    u12_partial_pair #(.W(width), .SHIFT0(8), .SHIFT1(9)) u_pair4 (
        .a_s(a_s),
        .bit0_en(b_s[8]),
        .bit1_en(b_s[9]),
        .pair_sum(stage0_pair4)
    );

    u12_partial_tail #(.W(width), .POS_SHIFT(10), .NEG_SHIFT(11)) u_tail (
        .a_s(a_s),
        .pos_en(b_s[10]),
        .neg_en(b_s[11]),
        .tail_sum(stage0_tail)
    );

    assign stage1_sum0 = stage0_pair0 + stage0_pair1;
    assign stage1_sum1 = stage0_pair2 + stage0_pair3;
    assign stage1_sum2 = stage0_pair4 + stage0_tail;

    assign stage2_sum0 = stage1_sum0 + stage1_sum1;
    assign stage2_sum1 = stage1_sum2;

    assign final_product = stage2_sum0 + stage2_sum1;
    assign P = final_product;
endmodule

module Multi_Booth_signed_odd #(
    parameter width = 11
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    wire [width+1:1] a_ext = {A[width], A[width:1]};
    wire [width+1:1] b_ext = {B[width], B[width:1]};
    wire [((width+1)*2):1] p_ext;

    Multi_Booth_signed_even #(.width(width + 1)) u_even (
        .A(a_ext),
        .B(b_ext),
        .P(p_ext)
    );

    assign P = p_ext[(width*2):1];
endmodule
