module DataReOrganize #(
    parameter data_width = 20,
    parameter a_tile_column_size = 4
) (
    input wire clk,
    input wire rst_n,
    input wire en,
    input wire [data_width * a_tile_column_size - 1:0] din,
    output reg [data_width * a_tile_column_size - 1:0] dout
);
    reg [data_width - 1:0] row0_delay;
    reg [data_width * 2 - 1:0] row1_delay;
    reg [data_width * 3 - 1:0] row2_delay;
    reg [data_width * 4 - 1:0] row3_delay;

    wire [data_width - 1:0] stage0_slice;
    wire [data_width - 1:0] stage1_slice;
    wire [data_width - 1:0] stage2_slice;
    wire [data_width - 1:0] stage3_slice;

    assign stage0_slice = row0_delay[data_width - 1:0];
    assign stage1_slice = row1_delay[data_width * 2 - 1:data_width];
    assign stage2_slice = row2_delay[data_width * 3 - 1:data_width * 2];
    assign stage3_slice = row3_delay[data_width * 4 - 1:data_width * 3];

    always @(negedge rst_n or posedge clk) begin
        if (!rst_n) begin
            row0_delay <= 'd0;
            row1_delay <= 'd0;
            row2_delay <= 'd0;
            row3_delay <= 'd0;
            dout <= 'd0;
        end else if (en) begin
            row0_delay[data_width - 1:0] <= din[data_width * 1 - 1:data_width * 0];
            row1_delay[data_width - 1:0] <= din[data_width * 2 - 1:data_width * 1];
            row2_delay[data_width - 1:0] <= din[data_width * 3 - 1:data_width * 2];
            row3_delay[data_width - 1:0] <= din[data_width * 4 - 1:data_width * 3];

            row1_delay[data_width * 2 - 1:data_width] <= row0_delay[data_width - 1:0];
            row2_delay[data_width * 3 - 1:data_width] <= row1_delay[data_width * 2 - 1:0];
            row3_delay[data_width * 4 - 1:data_width] <= row2_delay[data_width * 3 - 1:0];

            dout[data_width * 1 - 1:data_width * 0] <= stage0_slice;
            dout[data_width * 2 - 1:data_width * 1] <= stage1_slice;
            dout[data_width * 3 - 1:data_width * 2] <= stage2_slice;
            dout[data_width * 4 - 1:data_width * 3] <= stage3_slice;
        end
    end
endmodule
