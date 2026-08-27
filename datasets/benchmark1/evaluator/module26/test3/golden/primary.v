module pe_row_lane_wrapper #(
    parameter integer DATA_WIDTH = 24
) (
    input wire clk,
    input wire rst_n,
    input wire w_en,
    input wire w_compute,
    input wire [DATA_WIDTH - 1 : 0] lane_active_left,
    output wire [DATA_WIDTH - 1 : 0] lane_active_right,
    input wire [DATA_WIDTH - 1 : 0] lane_weight_above,
    output wire [DATA_WIDTH - 1 : 0] lane_weight_below,
    input wire [DATA_WIDTH * 2 - 1 : 0] lane_in_sum,
    output wire [DATA_WIDTH * 2 - 1 : 0] lane_out_sum
);
    PE #(.data_width(DATA_WIDTH)) lane_pe (
        .clk(clk),
        .rst_n(rst_n),
        .w_en(w_en),
        .w_compute(w_compute),
        .active_left(lane_active_left),
        .active_right(lane_active_right),
        .in_sum(lane_in_sum),
        .out_sum(lane_out_sum),
        .in_weight_above(lane_weight_above),
        .out_weight_below(lane_weight_below)
    );
endmodule

module PE_row #(
    parameter data_width = 24,
    parameter w_tile_column_size = 13
) (
    input wire clk,
    input wire rst_n,
    input wire w_en,
    input wire w_compute,
    input wire [data_width - 1 : 0] active_left,
    output wire [data_width - 1 : 0] active_right,
    input wire [data_width * w_tile_column_size - 1 : 0] in_weight_above,
    output wire [data_width * w_tile_column_size - 1 : 0] out_weight_below,
    input wire [data_width * 2 * w_tile_column_size - 1 : 0] in_sum,
    output wire [data_width * 2 * w_tile_column_size - 1 : 0] out_sum
);

    localparam integer SUM_WIDTH = data_width * 2;

    wire [data_width * (w_tile_column_size + 1) - 1 : 0] active_chain;
    wire [data_width * w_tile_column_size - 1 : 0] lane_weight_bus;
    wire [SUM_WIDTH * w_tile_column_size - 1 : 0] lane_sum_bus;
    wire [data_width * w_tile_column_size - 1 : 0] weight_route_bus;
    wire [SUM_WIDTH * w_tile_column_size - 1 : 0] sum_route_bus;
    genvar lane_idx;

    assign active_chain[data_width - 1 : 0] = active_left;
    assign out_weight_below = weight_route_bus;
    assign out_sum = sum_route_bus;

    generate
        for (lane_idx = w_tile_column_size - 1; lane_idx >= 0; lane_idx = lane_idx - 1) begin : lane
            wire [data_width - 1 : 0] lane_active_left;
            wire [data_width - 1 : 0] lane_active_right;
            wire [data_width - 1 : 0] lane_weight_in;
            wire [data_width - 1 : 0] lane_weight_out;
            wire [SUM_WIDTH - 1 : 0] lane_sum_in;
            wire [SUM_WIDTH - 1 : 0] lane_sum_out;
            wire [data_width - 1 : 0] slice;
            wire [data_width - 1 : 0] route;
            wire [data_width - 1 : 0] block_stage_weight;
            wire [SUM_WIDTH - 1 : 0] block_stage_sum;

            assign lane_active_left =
                active_chain[(lane_idx + 1) * data_width - 1 : lane_idx * data_width];
            assign slice =
                in_weight_above[(lane_idx + 1) * data_width - 1 : lane_idx * data_width];
            assign lane_weight_in = slice;
            assign lane_sum_in =
                in_sum[(lane_idx + 1) * SUM_WIDTH - 1 : lane_idx * SUM_WIDTH];

            pe_row_lane_wrapper #(.DATA_WIDTH(data_width)) lane_wrapper (
                .clk(clk),
                .rst_n(rst_n),
                .w_en(w_en),
                .w_compute(w_compute),
                .lane_active_left(lane_active_left),
                .lane_active_right(lane_active_right),
                .lane_weight_above(lane_weight_in),
                .lane_weight_below(lane_weight_out),
                .lane_in_sum(lane_sum_in),
                .lane_out_sum(lane_sum_out)
            );

            assign active_chain[(lane_idx + 2) * data_width - 1 : (lane_idx + 1) * data_width] =
                lane_active_right;
            assign route = lane_weight_out;
            assign block_stage_weight = route;
            assign block_stage_sum = lane_sum_out;
            assign lane_weight_bus[(lane_idx + 1) * data_width - 1 : lane_idx * data_width] =
                block_stage_weight;
            assign lane_sum_bus[(lane_idx + 1) * SUM_WIDTH - 1 : lane_idx * SUM_WIDTH] =
                block_stage_sum;
            assign weight_route_bus[(lane_idx + 1) * data_width - 1 : lane_idx * data_width] =
                lane_weight_bus[(lane_idx + 1) * data_width - 1 : lane_idx * data_width];
            assign sum_route_bus[(lane_idx + 1) * SUM_WIDTH - 1 : lane_idx * SUM_WIDTH] =
                lane_sum_bus[(lane_idx + 1) * SUM_WIDTH - 1 : lane_idx * SUM_WIDTH];
        end
    endgenerate

    assign active_right =
        active_chain[data_width * (w_tile_column_size + 1) - 1 : data_width * w_tile_column_size - 1];

endmodule
