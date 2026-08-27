module u27_medium_seed #(
    parameter weight_width = 72,
    parameter sum_width = 144
) (
    input wire [weight_width - 1:0] weight_in,
    input wire [sum_width - 1:0] sum_in,
    output wire [weight_width - 1:0] weight_lane,
    output wire [sum_width - 1:0] sum_lane
);
    assign weight_lane = weight_in;
    assign sum_lane = sum_in;
endmodule

module u27_medium_tail #(
    parameter width = 72
) (
    input wire [width - 1:0] lane_in,
    output wire [width - 1:0] lane_out
);
    assign lane_out = lane_in;
endmodule

module u27_medium_row_shell #(
    parameter data_width = 24,
    parameter w_tile_column_size = 3
) (
    input wire clk,
    input wire rst_n,
    input wire w_en,
    input wire w_compute,
    input wire [data_width - 1:0] active_left,
    output wire [data_width - 1:0] active_right,
    input wire [data_width * w_tile_column_size - 1:0] weight_in,
    output wire [data_width * w_tile_column_size - 1:0] weight_out,
    input wire [data_width * 2 * w_tile_column_size - 1:0] sum_in,
    output wire [data_width * 2 * w_tile_column_size - 1:0] sum_out
);
    wire [data_width - 1:0] stage0_active_right;
    wire [data_width * w_tile_column_size - 1:0] weight_lane;
    wire [data_width * 2 * w_tile_column_size - 1:0] sum_lane;

    PE_row #(
        .data_width(data_width),
        .w_tile_column_size(w_tile_column_size)
    ) pe_row_unit (
        .clk(clk),
        .rst_n(rst_n),
        .w_en(w_en),
        .w_compute(w_compute),
        .active_left(active_left),
        .active_right(stage0_active_right),
        .in_weight_above(weight_in),
        .out_weight_below(weight_lane),
        .in_sum(sum_in),
        .out_sum(sum_lane)
    );

    assign active_right = stage0_active_right;
    assign weight_out = weight_lane;
    assign sum_out = sum_lane;
endmodule

module PE_array #(
    parameter data_width = 24,
    parameter a_tile_row_size = 6,
    parameter w_tile_column_size = 3
) (
    input wire clk,
    input wire rst_n,
    input wire w_en,
    input wire w_compute,
    input wire [data_width * a_tile_row_size - 1:0] active_left,
    output wire [data_width * a_tile_row_size - 1:0] active_right,
    input wire [data_width * w_tile_column_size - 1:0] in_weight_above,
    output wire [data_width * w_tile_column_size - 1:0] out_weight_below,
    input wire [data_width * 2 * w_tile_column_size - 1:0] in_sum,
    output wire [data_width * 2 * w_tile_column_size - 1:0] out_sum
);
    wire [data_width * w_tile_column_size * (a_tile_row_size + 1) - 1:0] stage0_weight_bus;
    wire [data_width * 2 * w_tile_column_size * (a_tile_row_size + 1) - 1:0] stage0_sum_bus;
    wire [data_width * w_tile_column_size - 1:0] weight_lane;
    wire [data_width * 2 * w_tile_column_size - 1:0] sum_lane;

    u27_medium_seed #(
        .weight_width(data_width * w_tile_column_size),
        .sum_width(data_width * 2 * w_tile_column_size)
    ) seed_stage (
        .weight_in(in_weight_above),
        .sum_in(in_sum),
        .weight_lane(stage0_weight_bus[data_width * w_tile_column_size - 1:0]),
        .sum_lane(stage0_sum_bus[data_width * 2 * w_tile_column_size - 1:0])
    );

    genvar row_idx;
    generate
        for (row_idx = a_tile_row_size - 1; row_idx >= 0; row_idx = row_idx - 1) begin : gen_medium_rows
            u27_medium_row_shell #(
                .data_width(data_width),
                .w_tile_column_size(w_tile_column_size)
            ) row_shell (
                .clk(clk),
                .rst_n(rst_n),
                .w_en(w_en),
                .w_compute(w_compute),
                .active_left(active_left[(row_idx + 1) * data_width - 1:row_idx * data_width]),
                .active_right(active_right[(row_idx + 1) * data_width - 1:row_idx * data_width]),
                .weight_in(stage0_weight_bus[(row_idx + 1) * data_width * w_tile_column_size - 1:row_idx * data_width * w_tile_column_size]),
                .weight_out(stage0_weight_bus[(row_idx + 2) * data_width * w_tile_column_size - 1:(row_idx + 1) * data_width * w_tile_column_size]),
                .sum_in(stage0_sum_bus[(row_idx + 1) * data_width * 2 * w_tile_column_size - 1:row_idx * data_width * 2 * w_tile_column_size]),
                .sum_out(stage0_sum_bus[(row_idx + 2) * data_width * 2 * w_tile_column_size - 1:(row_idx + 1) * data_width * 2 * w_tile_column_size])
            );
        end
    endgenerate

    assign weight_lane = stage0_weight_bus[data_width * w_tile_column_size * (a_tile_row_size + 1) - 1:data_width * w_tile_column_size * a_tile_row_size];
    assign sum_lane = stage0_sum_bus[data_width * 2 * w_tile_column_size * (a_tile_row_size + 1) - 1:data_width * 2 * w_tile_column_size * a_tile_row_size];

    u27_medium_tail #(
        .width(data_width * w_tile_column_size)
    ) weight_tail (
        .lane_in(weight_lane),
        .lane_out(out_weight_below)
    );

    u27_medium_tail #(
        .width(data_width * 2 * w_tile_column_size)
    ) sum_tail (
        .lane_in(sum_lane),
        .lane_out(out_sum)
    );
endmodule
