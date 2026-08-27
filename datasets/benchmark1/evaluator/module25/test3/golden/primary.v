module pe_control_high #(
    parameter integer CTRL_WIDTH = 1
) (
    input wire w_en,
    input wire w_compute,
    output wire load_phase,
    output wire compute_phase,
    output wire hold_phase
);
    wire raw_load;
    wire raw_compute;

    assign raw_load = w_en;
    assign raw_compute = (~w_en) & w_compute;

    assign load_phase = raw_load;
    assign compute_phase = raw_compute;
    assign hold_phase = (~raw_load) & (~raw_compute);
endmodule

module pe_datapath_high #(
    parameter integer DATA_WIDTH = 23
) (
    input wire [DATA_WIDTH - 1 : 0] stored_weight,
    input wire [DATA_WIDTH - 1 : 0] active_left,
    input wire [DATA_WIDTH * 2 - 1 : 0] in_sum,
    output wire [DATA_WIDTH - 1 : 0] forwarded_active,
    output wire [DATA_WIDTH * 2 - 1 : 0] product_value,
    output wire [DATA_WIDTH * 2 - 1 : 0] sum_value
);
    wire [DATA_WIDTH * 2 - 1 : 0] widened_weight;
    wire [DATA_WIDTH * 2 - 1 : 0] widened_active;

    assign widened_weight = {{DATA_WIDTH{1'b0}}, stored_weight};
    assign widened_active = {{DATA_WIDTH{1'b0}}, active_left};
    assign forwarded_active = active_left;
    assign product_value = stored_weight * active_left;
    assign sum_value = product_value + in_sum;
endmodule

module PE #(
    parameter data_width = 23
)(
    input wire clk,
    input wire rst_n,
    input wire w_en,
    input wire w_compute,
    input wire [data_width - 1 : 0] active_left,
    output reg [data_width - 1 : 0] active_right,
    input wire [data_width * 2 - 1 : 0] in_sum,
    output reg [data_width * 2 - 1 : 0] out_sum,
    input wire [data_width - 1 : 0] in_weight_above,
    output reg [data_width - 1 : 0] out_weight_below
);

    wire load_phase;
    wire compute_phase;
    wire hold_phase;

    wire [data_width - 1 : 0] forwarded_active;
    wire [data_width * 2 - 1 : 0] datapath_product;
    wire [data_width * 2 - 1 : 0] datapath_sum;

    wire [data_width - 1 : 0] reset_active_value;
    wire [data_width - 1 : 0] reset_weight_value;
    wire [data_width * 2 - 1 : 0] reset_sum_value;

    reg [data_width - 1 : 0] next_active_right;
    reg [data_width - 1 : 0] next_out_weight_below;
    reg [data_width * 2 - 1 : 0] next_out_sum;

    reg [data_width * 2 - 1 : 0] selected_product;
    reg [data_width * 2 - 1 : 0] selected_sum;
    reg [data_width - 1 : 0] selected_active;

    pe_control_high ctrl_unit (
        .w_en(w_en),
        .w_compute(w_compute),
        .load_phase(load_phase),
        .compute_phase(compute_phase),
        .hold_phase(hold_phase)
    );

    pe_datapath_high #(.DATA_WIDTH(data_width)) data_unit (
        .stored_weight(out_weight_below),
        .active_left(active_left),
        .in_sum(in_sum),
        .forwarded_active(forwarded_active),
        .product_value(datapath_product),
        .sum_value(datapath_sum)
    );

    assign reset_active_value = {data_width{1'b0}};
    assign reset_weight_value = {data_width{1'b0}};
    assign reset_sum_value = {(data_width * 2){1'b0}};

    always @* begin
        next_active_right = active_right;
        next_out_weight_below = out_weight_below;
        next_out_sum = out_sum;

        selected_product = datapath_product;
        selected_sum = datapath_sum;
        selected_active = forwarded_active;

        if (load_phase) begin
            next_active_right = active_right;
            next_out_weight_below = in_weight_above;
            next_out_sum = out_sum;
        end

        if (compute_phase) begin
            next_active_right = selected_active;
            next_out_weight_below = out_weight_below;
            next_out_sum = selected_sum;
        end

        if (hold_phase) begin
            next_active_right = active_right;
            next_out_weight_below = out_weight_below;
            next_out_sum = out_sum;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_right <= reset_active_value;
            out_weight_below <= reset_weight_value;
            out_sum <= reset_sum_value;
        end else begin
            active_right <= next_active_right;
            out_weight_below <= next_out_weight_below;
            out_sum <= next_out_sum;
        end
    end

endmodule
