module MAC_signed #(
    parameter width = 22
) (
    input wire signed [width:1] A,
    input wire signed [width:1] B,
    input wire signed [width*2:1] acc_in,
    output wire signed [width*2+1:1] result
);
    wire signed [width*2:1] product_raw;
    wire signed [width*2+1:1] product_ext;
    wire signed [width*2+1:1] acc_ext;
    wire signed [width*2+1:1] sum_stage;
    wire signed [width*2+1:1] result_stage;

    assign product_raw = A * B;
    assign product_ext = {product_raw[width*2], product_raw};
    assign acc_ext = {acc_in[width*2], acc_in};
    assign sum_stage = product_ext + acc_ext;
    assign result_stage = sum_stage;
    assign result = result_stage;
endmodule
