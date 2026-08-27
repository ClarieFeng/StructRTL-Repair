module u21_medium_row_head #(
    parameter DATA_W = 20
) (
    input wire [DATA_W-1:0] input_slice,
    output wire [DATA_W-1:0] next_column_chain
);
    assign next_column_chain = input_slice;
endmodule

module u21_medium_row_stage #(
    parameter DATA_W = 20,
    parameter DEPTH = 2
) (
    input wire [DATA_W*DEPTH-1:0] prev_column_chain,
    input wire [DATA_W-1:0] input_slice,
    output wire [DATA_W*(DEPTH+1)-1:0] next_column_chain
);
    assign next_column_chain[DATA_W-1:0] = input_slice;
    assign next_column_chain[DATA_W*(DEPTH+1)-1:DATA_W] = prev_column_chain;
endmodule

module u21_medium_output_pick #(
    parameter DATA_W = 20,
    parameter DEPTH = 2
) (
    input wire [DATA_W*DEPTH-1:0] row_column_chain,
    output wire [DATA_W-1:0] output_slice
);
    assign output_slice = row_column_chain[DATA_W*DEPTH-1:DATA_W*(DEPTH-1)];
endmodule

module DataReOrganize #(
    parameter data_width = 20,
    parameter a_tile_column_size = 6
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
    reg [data_width * 5 - 1:0] row4_delay;
    reg [data_width * 6 - 1:0] row5_delay;

    wire [data_width-1:0] column0_slice;
    wire [data_width-1:0] column1_slice;
    wire [data_width-1:0] column2_slice;
    wire [data_width-1:0] column3_slice;
    wire [data_width-1:0] column4_slice;
    wire [data_width-1:0] column5_slice;

    wire [data_width-1:0] next_column_chain0;
    wire [data_width*2-1:0] next_column_chain1;
    wire [data_width*3-1:0] next_column_chain2;
    wire [data_width*4-1:0] next_column_chain3;
    wire [data_width*5-1:0] next_column_chain4;
    wire [data_width*6-1:0] next_column_chain5;

    wire [data_width-1:0] output_column0_slice;
    wire [data_width-1:0] output_column1_slice;
    wire [data_width-1:0] output_column2_slice;
    wire [data_width-1:0] output_column3_slice;
    wire [data_width-1:0] output_column4_slice;
    wire [data_width-1:0] output_column5_slice;

    assign column0_slice = din[data_width * 1 - 1:data_width * 0];
    assign column1_slice = din[data_width * 2 - 1:data_width * 1];
    assign column2_slice = din[data_width * 3 - 1:data_width * 2];
    assign column3_slice = din[data_width * 4 - 1:data_width * 3];
    assign column4_slice = din[data_width * 5 - 1:data_width * 4];
    assign column5_slice = din[data_width * 6 - 1:data_width * 5];

    u21_medium_row_head #(.DATA_W(data_width)) u_row0 (
        .input_slice(column0_slice),
        .next_column_chain(next_column_chain0)
    );

    u21_medium_row_stage #(.DATA_W(data_width), .DEPTH(1)) u_row1 (
        .prev_column_chain(row0_delay),
        .input_slice(column1_slice),
        .next_column_chain(next_column_chain1)
    );

    u21_medium_row_stage #(.DATA_W(data_width), .DEPTH(2)) u_row2 (
        .prev_column_chain(row1_delay),
        .input_slice(column2_slice),
        .next_column_chain(next_column_chain2)
    );

    u21_medium_row_stage #(.DATA_W(data_width), .DEPTH(3)) u_row3 (
        .prev_column_chain(row2_delay),
        .input_slice(column3_slice),
        .next_column_chain(next_column_chain3)
    );

    u21_medium_row_stage #(.DATA_W(data_width), .DEPTH(4)) u_row4 (
        .prev_column_chain(row3_delay),
        .input_slice(column4_slice),
        .next_column_chain(next_column_chain4)
    );

    u21_medium_row_stage #(.DATA_W(data_width), .DEPTH(5)) u_row5 (
        .prev_column_chain(row4_delay),
        .input_slice(column5_slice),
        .next_column_chain(next_column_chain5)
    );

    u21_medium_output_pick #(.DATA_W(data_width), .DEPTH(1)) u_out0 (.row_column_chain(row0_delay), .output_slice(output_column0_slice));
    u21_medium_output_pick #(.DATA_W(data_width), .DEPTH(2)) u_out1 (.row_column_chain(row1_delay), .output_slice(output_column1_slice));
    u21_medium_output_pick #(.DATA_W(data_width), .DEPTH(3)) u_out2 (.row_column_chain(row2_delay), .output_slice(output_column2_slice));
    u21_medium_output_pick #(.DATA_W(data_width), .DEPTH(4)) u_out3 (.row_column_chain(row3_delay), .output_slice(output_column3_slice));
    u21_medium_output_pick #(.DATA_W(data_width), .DEPTH(5)) u_out4 (.row_column_chain(row4_delay), .output_slice(output_column4_slice));
    u21_medium_output_pick #(.DATA_W(data_width), .DEPTH(6)) u_out5 (.row_column_chain(row5_delay), .output_slice(output_column5_slice));

    always @(negedge rst_n or posedge clk) begin
        if (!rst_n) begin
            row0_delay <= 'd0;
            row1_delay <= 'd0;
            row2_delay <= 'd0;
            row3_delay <= 'd0;
            row4_delay <= 'd0;
            row5_delay <= 'd0;
            dout <= 'd0;
        end else if (en) begin
            row0_delay <= next_column_chain0;
            row1_delay <= next_column_chain1;
            row2_delay <= next_column_chain2;
            row3_delay <= next_column_chain3;
            row4_delay <= next_column_chain4;
            row5_delay <= next_column_chain5;

            dout[data_width * 1 - 1:data_width * 0] <= output_column0_slice;
            dout[data_width * 2 - 1:data_width * 1] <= output_column1_slice;
            dout[data_width * 3 - 1:data_width * 2] <= output_column2_slice;
            dout[data_width * 4 - 1:data_width * 3] <= output_column3_slice;
            dout[data_width * 5 - 1:data_width * 4] <= output_column4_slice;
            dout[data_width * 6 - 1:data_width * 5] <= output_column5_slice;
        end
    end
endmodule
