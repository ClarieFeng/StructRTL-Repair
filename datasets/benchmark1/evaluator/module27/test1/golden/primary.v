module PE_array #(
    parameter data_width = 19,
    parameter a_tile_row_size = 4,
    parameter w_tile_column_size = 2
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
    wire [data_width * w_tile_column_size * (a_tile_row_size + 1) - 1:0] weight_bus;
    wire [data_width * 2 * w_tile_column_size * (a_tile_row_size + 1) - 1:0] sum_bus;

    assign weight_bus[data_width * w_tile_column_size - 1:0] = in_weight_above;
    assign sum_bus[data_width * 2 * w_tile_column_size - 1:0] = in_sum;

    genvar row_idx;
    generate
        for (row_idx = a_tile_row_size - 1; row_idx >= 0; row_idx = row_idx - 1) begin : gen_pe_rows
            PE_row #(
                .data_width(data_width),
                .w_tile_column_size(w_tile_column_size)
            ) pe_row_unit (
                .clk(clk),
                .rst_n(rst_n),
                .w_en(w_en),
                .w_compute(w_compute),
                .active_left(active_left[(row_idx + 1) * data_width - 1:row_idx * data_width]),
                .active_right(active_right[(row_idx + 1) * data_width - 1:row_idx * data_width]),
                .in_weight_above(weight_bus[(row_idx + 1) * data_width * w_tile_column_size - 1:row_idx * data_width * w_tile_column_size]),
                .out_weight_below(weight_bus[(row_idx + 2) * data_width * w_tile_column_size - 1:(row_idx + 1) * data_width * w_tile_column_size]),
                .in_sum(sum_bus[(row_idx + 1) * data_width * 2 * w_tile_column_size - 1:row_idx * data_width * 2 * w_tile_column_size]),
                .out_sum(sum_bus[(row_idx + 2) * data_width * 2 * w_tile_column_size - 1:(row_idx + 1) * data_width * 2 * w_tile_column_size])
            );
        end
    endgenerate

    assign out_weight_below = weight_bus[data_width * w_tile_column_size * (a_tile_row_size + 1) - 1:data_width * w_tile_column_size * a_tile_row_size];
    assign out_sum = sum_bus[data_width * 2 * w_tile_column_size * (a_tile_row_size + 1) - 1:data_width * 2 * w_tile_column_size * a_tile_row_size];
endmodule
