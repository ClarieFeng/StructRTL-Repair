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

    wire [data_width * (w_tile_column_size + 1) - 1 : 0] active_right_temp;
    wire [data_width * w_tile_column_size - 1 : 0] weight_lane;
    wire [SUM_WIDTH * w_tile_column_size - 1 : 0] sum_lane;
    wire [data_width * w_tile_column_size - 1 : 0] weight_route;
    wire [SUM_WIDTH * w_tile_column_size - 1 : 0] sum_route;
    genvar i;

    assign active_right_temp[data_width - 1 : 0] = active_left;
    assign out_weight_below = weight_route;
    assign out_sum = sum_route;

    generate
        for (i = w_tile_column_size - 1; i >= 0; i = i - 1) begin : column_lane
            wire [data_width - 1 : 0] lane_active_left;
            wire [data_width - 1 : 0] lane_active_right;
            wire [data_width - 1 : 0] lane_weight_slice;
            wire [data_width * 2 - 1 : 0] lane_sum_slice;
            wire [data_width - 1 : 0] lane_weight_route;
            wire [data_width * 2 - 1 : 0] lane_sum_route;

            assign lane_active_left =
                active_right_temp[(i + 1) * data_width - 1 : i * data_width];
            assign lane_weight_slice =
                in_weight_above[(i + 1) * data_width - 1 : i * data_width];
            assign lane_sum_slice =
                in_sum[(i + 1) * SUM_WIDTH - 1 : i * SUM_WIDTH];

            PE #(.data_width(data_width)) pe_lane (
                .clk(clk),
                .rst_n(rst_n),
                .w_en(w_en),
                .w_compute(w_compute),
                .active_left(lane_active_left),
                .active_right(lane_active_right),
                .in_sum(lane_sum_slice),
                .out_sum(lane_sum_route),
                .in_weight_above(lane_weight_slice),
                .out_weight_below(lane_weight_route)
            );

            assign active_right_temp[(i + 2) * data_width - 1 : (i + 1) * data_width] =
                lane_active_right;
            assign weight_lane[(i + 1) * data_width - 1 : i * data_width] =
                lane_weight_route;
            assign sum_lane[(i + 1) * SUM_WIDTH - 1 : i * SUM_WIDTH] =
                lane_sum_route;
            assign weight_route[(i + 1) * data_width - 1 : i * data_width] =
                weight_lane[(i + 1) * data_width - 1 : i * data_width];
            assign sum_route[(i + 1) * SUM_WIDTH - 1 : i * SUM_WIDTH] =
                sum_lane[(i + 1) * SUM_WIDTH - 1 : i * SUM_WIDTH];
        end
    endgenerate

    assign active_right =
        active_right_temp[data_width * (w_tile_column_size + 1) - 1 : data_width * w_tile_column_size - 1];

endmodule
