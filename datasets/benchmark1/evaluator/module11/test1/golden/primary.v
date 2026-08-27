module u11_triplet_sum #(
    parameter width = 17
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire [width:1] C,
    output wire [width+2:1] S
);
    assign S = {2'b0, A} + {2'b0, B} + {2'b0, C};
endmodule

module u11_pair_sum #(
    parameter width = 19
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width+1:1] S
);
    assign S = {1'b0, A} + {1'b0, B};
endmodule

module addertree_17_6_CLA #(
    parameter width = 17
) (
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    input wire [width:1] A6,
    output wire [width + 3:1] S
);
    wire [width+2:1] g0;
    wire [width+2:1] g1;

    u11_triplet_sum #(.width(width)) u0 (.A(A1), .B(A2), .C(A3), .S(g0));
    u11_triplet_sum #(.width(width)) u1 (.A(A4), .B(A5), .C(A6), .S(g1));
    u11_pair_sum #(.width(width+2)) u2 (.A(g0), .B(g1), .S(S));
endmodule

