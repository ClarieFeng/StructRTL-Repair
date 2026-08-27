module u11_triplet_sum #(
    parameter width = 19
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire [width:1] C,
    output wire [width+2:1] S
);
    assign S = {2'b0, A} + {2'b0, B} + {2'b0, C};
endmodule

module u11_pair_sum #(
    parameter width = 21
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width+1:1] S
);
    assign S = {1'b0, A} + {1'b0, B};
endmodule

module u11_reduce_three_blocks #(
    parameter width = 19
) (
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    input wire [width:1] A6,
    input wire [width:1] A7,
    input wire [width:1] A8,
    input wire [width:1] A9,
    output wire [width+4:1] S
);
    wire [width+2:1] g0;
    wire [width+2:1] g1;
    wire [width+2:1] g2;
    wire [width+3:1] h0;

    u11_triplet_sum #(.width(width)) u0 (.A(A1), .B(A2), .C(A3), .S(g0));
    u11_triplet_sum #(.width(width)) u1 (.A(A4), .B(A5), .C(A6), .S(g1));
    u11_triplet_sum #(.width(width)) u2 (.A(A7), .B(A8), .C(A9), .S(g2));
    u11_pair_sum #(.width(width+2)) u3 (.A(g0), .B(g1), .S(h0));
    u11_pair_sum #(.width(width+3)) u4 (.A(h0), .B(g2), .S(S));
endmodule

module addertree_19_9_PPA_Sklansky #(
    parameter width = 19
) (
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    input wire [width:1] A6,
    input wire [width:1] A7,
    input wire [width:1] A8,
    input wire [width:1] A9,
    output wire [width + 4:1] S
);
    u11_reduce_three_blocks #(.width(width)) u0 (
        .A1(A1), .A2(A2), .A3(A3),
        .A4(A4), .A5(A5), .A6(A6),
        .A7(A7), .A8(A8), .A9(A9),
        .S(S)
    );
endmodule

