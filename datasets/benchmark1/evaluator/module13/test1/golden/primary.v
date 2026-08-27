module u13_low_mul_core #(
    parameter width = 6
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    wire [width-1:0] a_u;
    wire [width-1:0] b_u;
    wire [(width*2)-1:0] product_u;
    wire [(width*2)-1:0] product_copy;

    assign a_u = A[width:1];
    assign b_u = B[width:1];
    assign product_u = a_u * b_u;
    assign product_copy = product_u;
    assign P = product_copy;
endmodule

module Multi_Booth_unsigned #(
    parameter width = 6
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    u13_low_mul_core #(.width(width)) u_core (
        .A(A),
        .B(B),
        .P(P)
    );
endmodule
