module u14_low_mul_core #(
    parameter width = 6
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    wire signed [width-1:0] a_s;
    wire signed [width-1:0] b_s;
    wire signed [(width*2)-1:0] product_s;
    wire signed [(width*2)-1:0] product_copy;

    assign a_s = A[width:1];
    assign b_s = B[width:1];
    assign product_s = a_s * b_s;
    assign product_copy = product_s;
    assign P = product_copy;
endmodule

module Multi_signed #(
    parameter width = 6
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    u14_low_mul_core #(.width(width)) u_core (
        .A(A),
        .B(B),
        .P(P)
    );
endmodule
