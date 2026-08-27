module PE#(
    parameter data_width = 22
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

    wire [data_width * 2 - 1 : 0] multiply_stage;
    wire [data_width * 2 - 1 : 0] accumulate_stage;
    wire [data_width - 1 : 0] forward_stage;

    reg [data_width - 1 : 0] next_active_right;
    reg [data_width - 1 : 0] next_out_weight_below;
    reg [data_width * 2 - 1 : 0] next_out_sum;

    reg load_phase;
    reg compute_phase;
    reg hold_phase;

    assign multiply_stage = in_weight_above * active_left;
    assign accumulate_stage = out_sum + multiply_stage;
    assign forward_stage = active_left;

    always @* begin
        load_phase = 1'b0;
        compute_phase = 1'b0;
        hold_phase = 1'b0;

        if (w_en) begin
            load_phase = 1'b1;
        end else if (w_compute) begin
            compute_phase = 1'b1;
        end else begin
            hold_phase = 1'b1;
        end

        next_active_right = active_right;
        next_out_weight_below = out_weight_below;
        next_out_sum = out_sum;

        if (load_phase) begin
            next_active_right = active_right;
            next_out_weight_below = out_weight_below;
            next_out_sum = in_sum;
        end

        if (compute_phase) begin
            next_active_right = forward_stage;
            next_out_weight_below = in_weight_above;
            next_out_sum = accumulate_stage;
        end

        if (hold_phase) begin
            next_active_right = active_right;
            next_out_weight_below = out_weight_below;
            next_out_sum = out_sum;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_weight_below <= {data_width{1'b0}};
            active_right <= {data_width{1'b0}};
            out_sum <= {(data_width * 2){1'b0}};
        end else begin
            out_weight_below <= next_out_weight_below;
            active_right <= next_active_right;
            out_sum <= next_out_sum;
        end
    end

endmodule
