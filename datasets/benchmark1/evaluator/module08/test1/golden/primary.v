module AdderTree_signed #(
    parameter width = 17
)(
    input  wire [width:1] A1,
    input  wire [width:1] A2,
    input  wire [width:1] A3,
    input  wire [width:1] A4,
    input  wire [width:1] A5,
    input  wire [width:1] A6,
    input  wire [width:1] A7,
    input  wire [width:1] A8,
    input  wire [width:1] A9,
    input  wire [width:1] A10,
    output wire [width+4:1] S
);

    localparam SW = width + 4;

    wire signed [SW-1:0] a1_s;
    wire signed [SW-1:0] a2_s;
    wire signed [SW-1:0] a3_s;
    wire signed [SW-1:0] a4_s;
    wire signed [SW-1:0] a5_s;
    wire signed [SW-1:0] a6_s;
    wire signed [SW-1:0] a7_s;
    wire signed [SW-1:0] a8_s;
    wire signed [SW-1:0] a9_s;
    wire signed [SW-1:0] a10_s;

    assign a1_s  = {{(SW-width){A1[width]}},  A1};
    assign a2_s  = {{(SW-width){A2[width]}},  A2};
    assign a3_s  = {{(SW-width){A3[width]}},  A3};
    assign a4_s  = {{(SW-width){A4[width]}},  A4};
    assign a5_s  = {{(SW-width){A5[width]}},  A5};
    assign a6_s  = {{(SW-width){A6[width]}},  A6};
    assign a7_s  = {{(SW-width){A7[width]}},  A7};
    assign a8_s  = {{(SW-width){A8[width]}},  A8};
    assign a9_s  = {{(SW-width){A9[width]}},  A9};
    assign a10_s = {{(SW-width){A10[width]}}, A10};

    wire signed [SW-1:0] sum_1_0;
    wire signed [SW-1:0] sum_1_1;
    wire signed [SW-1:0] sum_1_2;
    wire signed [SW-1:0] sum_1_3;
    wire signed [SW-1:0] sum_2_0;
    wire signed [SW-1:0] sum_2_1;
    wire signed [SW-1:0] sum_3_0;
    wire signed [SW-1:0] sum_final;

    assign sum_1_0 = a1_s  + a2_s;
    assign sum_1_1 = a3_s  + a4_s;
    assign sum_1_2 = a5_s  + a6_s;
    assign sum_1_3 = a7_s  + a8_s;

    assign sum_2_0 = sum_1_0 + sum_1_1;
    assign sum_2_1 = sum_1_2 + sum_1_3;

    assign sum_3_0 = sum_2_0 + sum_2_1;

    assign sum_final = sum_3_0 + a9_s + a10_s;

    assign S = sum_final;

endmodule
