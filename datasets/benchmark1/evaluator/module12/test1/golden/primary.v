module u12_low_mul_core #(
    parameter width = 8
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    wire signed [width-1:0] a_s = A[width:1];
    wire signed [width-1:0] b_s = B[width:1];
    wire signed [(width*2)-1:0] product_s = a_s * b_s;
    wire signed [(width*2)-1:0] product_copy = product_s;

    assign P = product_copy;
endmodule

module Multi_Booth_signed_even #(
    parameter width = 8
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    u12_low_mul_core #(.width(width)) u_core (
        .A(A),
        .B(B),
        .P(P)
    );
endmodule

module Multi_Booth_signed_odd #(
    parameter width = 7
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
