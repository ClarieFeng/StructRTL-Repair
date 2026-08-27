module u13_partial_pair #(
    parameter W = 6,
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

module Multi_Booth_unsigned #(
    parameter width = 6
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    wire [width-1:0] a_u;
    wire [width-1:0] b_u;

    wire [(width*2)-1:0] stage0_pair0;
    wire [(width*2)-1:0] stage0_pair1;
    wire [(width*2)-1:0] stage0_pair2;

    wire [(width*2)-1:0] stage0_alias0;
    wire [(width*2)-1:0] stage0_alias1;
    wire [(width*2)-1:0] stage0_alias2;

    wire [(width*2)-1:0] stage1_sum0;
    wire [(width*2)-1:0] stage1_alias0;
    wire [(width*2)-1:0] final_product;

    assign a_u = A[width:1];
    assign b_u = B[width:1];

    u13_partial_pair #(.W(width), .SHIFT0(0), .SHIFT1(1)) u_pair0 (
        .a_u(a_u),
        .bit0_en(b_u[0]),
        .bit1_en(b_u[1]),
        .pair_sum(stage0_pair0)
    );

    u13_partial_pair #(.W(width), .SHIFT0(2), .SHIFT1(3)) u_pair1 (
        .a_u(a_u),
        .bit0_en(b_u[2]),
        .bit1_en(b_u[3]),
        .pair_sum(stage0_pair1)
    );

    u13_partial_pair #(.W(width), .SHIFT0(4), .SHIFT1(5)) u_pair2 (
        .a_u(a_u),
        .bit0_en(b_u[4]),
        .bit1_en(b_u[5]),
        .pair_sum(stage0_pair2)
    );

    assign stage0_alias0 = stage0_pair0;
    assign stage0_alias1 = stage0_pair1;
    assign stage0_alias2 = stage0_pair2;

    assign stage1_sum0 = stage0_alias0 + stage0_alias1;
    assign stage1_alias0 = stage1_sum0;
    assign final_product = stage1_alias0 + stage0_alias2;
    assign P = final_product;
endmodule
