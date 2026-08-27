module u21_high_input_slice #(
    parameter DATA_W = 24,
    parameter COLUMN_INDEX = 0
) (
    input wire [DATA_W * 8 - 1:0] input_bus,
    output wire [DATA_W-1:0] column_slice,
    output wire [DATA_W-1:0] column_slice_alias
);
    assign column_slice = input_bus[DATA_W * (COLUMN_INDEX + 1) - 1:DATA_W * COLUMN_INDEX];
    assign column_slice_alias = column_slice;
endmodule

module u21_high_row_head #(
    parameter DATA_W = 24
) (
    input wire [DATA_W-1:0] input_slice,
    output wire [DATA_W-1:0] next_stage_chain,
    output wire [DATA_W-1:0] next_stage_alias
);
    assign next_stage_chain = input_slice;
    assign next_stage_alias = next_stage_chain;
endmodule

module u21_high_row_stage #(
    parameter DATA_W = 24,
    parameter DEPTH = 2
) (
    input wire [DATA_W*DEPTH-1:0] prev_stage_chain,
    input wire [DATA_W-1:0] input_slice,
    output wire [DATA_W*(DEPTH+1)-1:0] next_stage_chain,
    output wire [DATA_W*(DEPTH+1)-1:0] next_stage_alias
);
    assign next_stage_chain[DATA_W-1:0] = input_slice;
    assign next_stage_chain[DATA_W*(DEPTH+1)-1:DATA_W] = prev_stage_chain;
    assign next_stage_alias = next_stage_chain;
endmodule

module u21_high_output_pick #(
    parameter DATA_W = 24,
    parameter DEPTH = 2
) (
    input wire [DATA_W*DEPTH-1:0] row_stage_chain,
    output wire [DATA_W-1:0] output_slice,
    output wire [DATA_W-1:0] output_slice_alias
);
    assign output_slice = row_stage_chain[DATA_W*DEPTH-1:DATA_W*(DEPTH-1)];
    assign output_slice_alias = output_slice;
endmodule

module DataReOrganize #(
    parameter data_width = 24,
    parameter a_tile_column_size = 8
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
    reg [data_width * 7 - 1:0] row6_delay;
    reg [data_width * 8 - 1:0] row7_delay;

    wire [data_width-1:0] column_slice0;
    wire [data_width-1:0] column_slice1;
    wire [data_width-1:0] column_slice2;
    wire [data_width-1:0] column_slice3;
    wire [data_width-1:0] column_slice4;
    wire [data_width-1:0] column_slice5;
    wire [data_width-1:0] column_slice6;
    wire [data_width-1:0] column_slice7;

    wire [data_width-1:0] column_alias0;
    wire [data_width-1:0] column_alias1;
    wire [data_width-1:0] column_alias2;
    wire [data_width-1:0] column_alias3;
    wire [data_width-1:0] column_alias4;
    wire [data_width-1:0] column_alias5;
    wire [data_width-1:0] column_alias6;
    wire [data_width-1:0] column_alias7;

    wire [data_width-1:0] next_stage0;
    wire [data_width-1:0] next_alias0;
    wire [data_width*2-1:0] next_stage1;
    wire [data_width*2-1:0] next_alias1;
    wire [data_width*3-1:0] next_stage2;
    wire [data_width*3-1:0] next_alias2;
    wire [data_width*4-1:0] next_stage3;
    wire [data_width*4-1:0] next_alias3;
    wire [data_width*5-1:0] next_stage4;
    wire [data_width*5-1:0] next_alias4;
    wire [data_width*6-1:0] next_stage5;
    wire [data_width*6-1:0] next_alias5;
    wire [data_width*7-1:0] next_stage6;
    wire [data_width*7-1:0] next_alias6;
    wire [data_width*8-1:0] next_stage7;
    wire [data_width*8-1:0] next_alias7;

    wire [data_width-1:0] output_slice0;
    wire [data_width-1:0] output_slice1;
    wire [data_width-1:0] output_slice2;
    wire [data_width-1:0] output_slice3;
    wire [data_width-1:0] output_slice4;
    wire [data_width-1:0] output_slice5;
    wire [data_width-1:0] output_slice6;
    wire [data_width-1:0] output_slice7;

    wire [data_width-1:0] output_alias0;
    wire [data_width-1:0] output_alias1;
    wire [data_width-1:0] output_alias2;
    wire [data_width-1:0] output_alias3;
    wire [data_width-1:0] output_alias4;
    wire [data_width-1:0] output_alias5;
    wire [data_width-1:0] output_alias6;
    wire [data_width-1:0] output_alias7;

    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(0)) u_in0 (.input_bus(din), .column_slice(column_slice0), .column_slice_alias(column_alias0));
    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(1)) u_in1 (.input_bus(din), .column_slice(column_slice1), .column_slice_alias(column_alias1));
    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(2)) u_in2 (.input_bus(din), .column_slice(column_slice2), .column_slice_alias(column_alias2));
    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(3)) u_in3 (.input_bus(din), .column_slice(column_slice3), .column_slice_alias(column_alias3));
    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(4)) u_in4 (.input_bus(din), .column_slice(column_slice4), .column_slice_alias(column_alias4));
    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(5)) u_in5 (.input_bus(din), .column_slice(column_slice5), .column_slice_alias(column_alias5));
    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(6)) u_in6 (.input_bus(din), .column_slice(column_slice6), .column_slice_alias(column_alias6));
    u21_high_input_slice #(.DATA_W(data_width), .COLUMN_INDEX(7)) u_in7 (.input_bus(din), .column_slice(column_slice7), .column_slice_alias(column_alias7));

    u21_high_row_head #(.DATA_W(data_width)) u_row0 (.input_slice(column_alias0), .next_stage_chain(next_stage0), .next_stage_alias(next_alias0));
    u21_high_row_stage #(.DATA_W(data_width), .DEPTH(1)) u_row1 (.prev_stage_chain(row0_delay), .input_slice(column_alias1), .next_stage_chain(next_stage1), .next_stage_alias(next_alias1));
    u21_high_row_stage #(.DATA_W(data_width), .DEPTH(2)) u_row2 (.prev_stage_chain(row1_delay), .input_slice(column_alias2), .next_stage_chain(next_stage2), .next_stage_alias(next_alias2));
    u21_high_row_stage #(.DATA_W(data_width), .DEPTH(3)) u_row3 (.prev_stage_chain(row2_delay), .input_slice(column_alias3), .next_stage_chain(next_stage3), .next_stage_alias(next_alias3));
    u21_high_row_stage #(.DATA_W(data_width), .DEPTH(4)) u_row4 (.prev_stage_chain(row3_delay), .input_slice(column_alias4), .next_stage_chain(next_stage4), .next_stage_alias(next_alias4));
    u21_high_row_stage #(.DATA_W(data_width), .DEPTH(5)) u_row5 (.prev_stage_chain(row4_delay), .input_slice(column_alias5), .next_stage_chain(next_stage5), .next_stage_alias(next_alias5));
    u21_high_row_stage #(.DATA_W(data_width), .DEPTH(6)) u_row6 (.prev_stage_chain(row5_delay), .input_slice(column_alias6), .next_stage_chain(next_stage6), .next_stage_alias(next_alias6));
    u21_high_row_stage #(.DATA_W(data_width), .DEPTH(7)) u_row7 (.prev_stage_chain(row6_delay), .input_slice(column_alias7), .next_stage_chain(next_stage7), .next_stage_alias(next_alias7));

    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(1)) u_out0 (.row_stage_chain(row0_delay), .output_slice(output_slice0), .output_slice_alias(output_alias0));
    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(2)) u_out1 (.row_stage_chain(row1_delay), .output_slice(output_slice1), .output_slice_alias(output_alias1));
    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(3)) u_out2 (.row_stage_chain(row2_delay), .output_slice(output_slice2), .output_slice_alias(output_alias2));
    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(4)) u_out3 (.row_stage_chain(row3_delay), .output_slice(output_slice3), .output_slice_alias(output_alias3));
    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(5)) u_out4 (.row_stage_chain(row4_delay), .output_slice(output_slice4), .output_slice_alias(output_alias4));
    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(6)) u_out5 (.row_stage_chain(row5_delay), .output_slice(output_slice5), .output_slice_alias(output_alias5));
    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(7)) u_out6 (.row_stage_chain(row6_delay), .output_slice(output_slice6), .output_slice_alias(output_alias6));
    u21_high_output_pick #(.DATA_W(data_width), .DEPTH(8)) u_out7 (.row_stage_chain(row7_delay), .output_slice(output_slice7), .output_slice_alias(output_alias7));

    always @(negedge rst_n or posedge clk) begin
        if (!rst_n) begin
            row0_delay <= 'd0;
            row1_delay <= 'd0;
            row2_delay <= 'd0;
            row3_delay <= 'd0;
            row4_delay <= 'd0;
            row5_delay <= 'd0;
            row6_delay <= 'd0;
            row7_delay <= 'd0;
            dout <= 'd0;
        end else if (en) begin
            row0_delay <= next_alias0;
            row1_delay <= next_alias1;
            row2_delay <= next_alias2;
            row3_delay <= next_alias3;
            row4_delay <= next_alias4;
            row5_delay <= next_alias5;
            row6_delay <= next_alias6;
            row7_delay <= next_alias7;

            dout[data_width * 1 - 1:data_width * 0] <= output_alias0;
            dout[data_width * 2 - 1:data_width * 1] <= output_alias1;
            dout[data_width * 3 - 1:data_width * 2] <= output_alias2;
            dout[data_width * 4 - 1:data_width * 3] <= output_alias3;
            dout[data_width * 5 - 1:data_width * 4] <= output_alias4;
            dout[data_width * 6 - 1:data_width * 5] <= output_alias5;
            dout[data_width * 7 - 1:data_width * 6] <= output_alias6;
            dout[data_width * 8 - 1:data_width * 7] <= output_alias7;
        end
    end
endmodule
