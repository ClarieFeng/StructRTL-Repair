module C_Sel_A_20bit #(
    parameter width = 20
) (
    input  wire [width:1] A,
    input  wire [width:1] B,
    input  wire           cin,
    output wire [width:1] S,
    output wire           cout
);

    wire [width:1] sum_int;

    assign S = sum_int;

    /* stage 0 : bits [4:1] ripple from cin */
    wire c0_0;
    wire c0_1;
    wire c0_2;
    wire c0_3;
    wire c0_4;

    assign c0_0     = cin;
    assign sum_int[1] = A[1] ^ B[1] ^ c0_0;
    assign c0_1     = (A[1] & B[1]) | (A[1] & c0_0) | (B[1] & c0_0);

    assign sum_int[2] = A[2] ^ B[2] ^ c0_1;
    assign c0_2     = (A[2] & B[2]) | (A[2] & c0_1) | (B[2] & c0_1);

    assign sum_int[3] = A[3] ^ B[3] ^ c0_2;
    assign c0_3     = (A[3] & B[3]) | (A[3] & c0_2) | (B[3] & c0_2);

    assign sum_int[4] = A[4] ^ B[4] ^ c0_3;
    assign c0_4     = (A[4] & B[4]) | (A[4] & c0_3) | (B[4] & c0_3);

    /* stage 1 : bits [8:5], precompute for carry-in 0 and 1 */
    wire [8:5] sum0_stage1;
    wire [8:5] sum1_stage1;
    wire carry0_stage1;
    wire carry1_stage1;
    wire select_stage1;

    wire s1_c0_5;
    wire s1_c0_6;
    wire s1_c0_7;
    wire s1_c0_8;

    wire s1_c1_5;
    wire s1_c1_6;
    wire s1_c1_7;
    wire s1_c1_8;

    assign s1_c0_5      = 1'b0;
    assign sum0_stage1[5] = A[5] ^ B[5] ^ s1_c0_5;
    assign s1_c0_6      = (A[5] & B[5]) | (A[5] & s1_c0_5) | (B[5] & s1_c0_5);
    assign sum0_stage1[6] = A[6] ^ B[6] ^ s1_c0_6;
    assign s1_c0_7      = (A[6] & B[6]) | (A[6] & s1_c0_6) | (B[6] & s1_c0_6);
    assign sum0_stage1[7] = A[7] ^ B[7] ^ s1_c0_7;
    assign s1_c0_8      = (A[7] & B[7]) | (A[7] & s1_c0_7) | (B[7] & s1_c0_7);
    assign sum0_stage1[8] = A[8] ^ B[8] ^ s1_c0_8;
    assign carry0_stage1 = (A[8] & B[8]) | (A[8] & s1_c0_8) | (B[8] & s1_c0_8);

    assign s1_c1_5      = 1'b1;
    assign sum1_stage1[5] = A[5] ^ B[5] ^ s1_c1_5;
    assign s1_c1_6      = (A[5] & B[5]) | (A[5] & s1_c1_5) | (B[5] & s1_c1_5);
    assign sum1_stage1[6] = A[6] ^ B[6] ^ s1_c1_6;
    assign s1_c1_7      = (A[6] & B[6]) | (A[6] & s1_c1_6) | (B[6] & s1_c1_6);
    assign sum1_stage1[7] = A[7] ^ B[7] ^ s1_c1_7;
    assign s1_c1_8      = (A[7] & B[7]) | (A[7] & s1_c1_7) | (B[7] & s1_c1_7);
    assign sum1_stage1[8] = A[8] ^ B[8] ^ s1_c1_8;
    assign carry1_stage1 = (A[8] & B[8]) | (A[8] & s1_c1_8) | (B[8] & s1_c1_8);

    assign select_stage1 = c0_4;

    assign sum_int[5] = select_stage1 ? sum1_stage1[5] : sum0_stage1[5];
    assign sum_int[6] = select_stage1 ? sum1_stage1[6] : sum0_stage1[6];
    assign sum_int[7] = select_stage1 ? sum1_stage1[7] : sum0_stage1[7];
    assign sum_int[8] = select_stage1 ? sum1_stage1[8] : sum0_stage1[8];

    wire carry_stage1_selected;
    assign carry_stage1_selected = select_stage1 ? carry1_stage1 : carry0_stage1;

    /* stage 2 : bits [12:9], precompute for carry-in 0 and 1 */
    wire [12:9] sum0_stage2;
    wire [12:9] sum1_stage2;
    wire carry0_stage2;
    wire carry1_stage2;
    wire select_stage2;

    wire s2_c0_9;
    wire s2_c0_10;
    wire s2_c0_11;
    wire s2_c0_12;

    wire s2_c1_9;
    wire s2_c1_10;
    wire s2_c1_11;
    wire s2_c1_12;

    assign s2_c0_9       = 1'b0;
    assign sum0_stage2[9]  = A[9]  ^ B[9]  ^ s2_c0_9;
    assign s2_c0_10      = (A[9]  & B[9])  | (A[9]  & s2_c0_9)  | (B[9]  & s2_c0_9);
    assign sum0_stage2[10] = A[10] ^ B[10] ^ s2_c0_10;
    assign s2_c0_11      = (A[10] & B[10]) | (A[10] & s2_c0_10) | (B[10] & s2_c0_10);
    assign sum0_stage2[11] = A[11] ^ B[11] ^ s2_c0_11;
    assign s2_c0_12      = (A[11] & B[11]) | (A[11] & s2_c0_11) | (B[11] & s2_c0_11);
    assign sum0_stage2[12] = A[12] ^ B[12] ^ s2_c0_12;
    assign carry0_stage2 = (A[12] & B[12]) | (A[12] & s2_c0_12) | (B[12] & s2_c0_12);

    assign s2_c1_9       = 1'b1;
    assign sum1_stage2[9]  = A[9]  ^ B[9]  ^ s2_c1_9;
    assign s2_c1_10      = (A[9]  & B[9])  | (A[9]  & s2_c1_9)  | (B[9]  & s2_c1_9);
    assign sum1_stage2[10] = A[10] ^ B[10] ^ s2_c1_10;
    assign s2_c1_11      = (A[10] & B[10]) | (A[10] & s2_c1_10) | (B[10] & s2_c1_10);
    assign sum1_stage2[11] = A[11] ^ B[11] ^ s2_c1_11;
    assign s2_c1_12      = (A[11] & B[11]) | (A[11] & s2_c1_11) | (B[11] & s2_c1_11);
    assign sum1_stage2[12] = A[12] ^ B[12] ^ s2_c1_12;
    assign carry1_stage2 = (A[12] & B[12]) | (A[12] & s2_c1_12) | (B[12] & s2_c1_12);

    assign select_stage2 = carry_stage1_selected;

    assign sum_int[9]  = select_stage2 ? sum1_stage2[9]  : sum0_stage2[9];
    assign sum_int[10] = select_stage2 ? sum1_stage2[10] : sum0_stage2[10];
    assign sum_int[11] = select_stage2 ? sum1_stage2[11] : sum0_stage2[11];
    assign sum_int[12] = select_stage2 ? sum1_stage2[12] : sum0_stage2[12];

    wire carry_stage2_selected;
    assign carry_stage2_selected = select_stage2 ? carry1_stage2 : carry0_stage2;

    /* stage 3 : bits [16:13], precompute for carry-in 0 and 1 */
    wire [16:13] sum0_stage3;
    wire [16:13] sum1_stage3;
    wire carry0_stage3;
    wire carry1_stage3;
    wire select_stage3;

    wire s3_c0_13;
    wire s3_c0_14;
    wire s3_c0_15;
    wire s3_c0_16;

    wire s3_c1_13;
    wire s3_c1_14;
    wire s3_c1_15;
    wire s3_c1_16;

    assign s3_c0_13       = 1'b0;
    assign sum0_stage3[13] = A[13] ^ B[13] ^ s3_c0_13;
    assign s3_c0_14       = (A[13] & B[13]) | (A[13] & s3_c0_13) | (B[13] & s3_c0_13);
    assign sum0_stage3[14] = A[14] ^ B[14] ^ s3_c0_14;
    assign s3_c0_15       = (A[14] & B[14]) | (A[14] & s3_c0_14) | (B[14] & s3_c0_14);
    assign sum0_stage3[15] = A[15] ^ B[15] ^ s3_c0_15;
    assign s3_c0_16       = (A[15] & B[15]) | (A[15] & s3_c0_15) | (B[15] & s3_c0_15);
    assign sum0_stage3[16] = A[16] ^ B[16] ^ s3_c0_16;
    assign carry0_stage3 = (A[16] & B[16]) | (A[16] & s3_c0_16) | (B[16] & s3_c0_16);

    assign s3_c1_13       = 1'b1;
    assign sum1_stage3[13] = A[13] ^ B[13] ^ s3_c1_13;
    assign s3_c1_14       = (A[13] & B[13]) | (A[13] & s3_c1_13) | (B[13] & s3_c1_13);
    assign sum1_stage3[14] = A[14] ^ B[14] ^ s3_c1_14;
    assign s3_c1_15       = (A[14] & B[14]) | (A[14] & s3_c1_14) | (B[14] & s3_c1_14);
    assign sum1_stage3[15] = A[15] ^ B[15] ^ s3_c1_15;
    assign s3_c1_16       = (A[15] & B[15]) | (A[15] & s3_c1_15) | (B[15] & s3_c1_15);
    assign sum1_stage3[16] = A[16] ^ B[16] ^ s3_c1_16;
    assign carry1_stage3 = (A[16] & B[16]) | (A[16] & s3_c1_16) | (B[16] & s3_c1_16);

    assign select_stage3 = carry_stage2_selected;

    assign sum_int[13] = select_stage3 ? sum1_stage3[13] : sum0_stage3[13];
    assign sum_int[14] = select_stage3 ? sum1_stage3[14] : sum0_stage3[14];
    assign sum_int[15] = select_stage3 ? sum1_stage3[15] : sum0_stage3[15];
    assign sum_int[16] = select_stage3 ? sum1_stage3[16] : sum0_stage3[16];

    wire carry_stage3_selected;
    assign carry_stage3_selected = select_stage3 ? carry1_stage3 : carry0_stage3;

    /* stage 4 : bits [20:17], precompute for carry-in 0 and 1 */
    wire [20:17] sum0_stage4;
    wire [20:17] sum1_stage4;
    wire carry0_stage4;
    wire carry1_stage4;
    wire select_stage4;

    wire s4_c0_17;
    wire s4_c0_18;
    wire s4_c0_19;
    wire s4_c0_20;

    wire s4_c1_17;
    wire s4_c1_18;
    wire s4_c1_19;
    wire s4_c1_20;

    assign s4_c0_17       = 1'b0;
    assign sum0_stage4[17] = A[17] ^ B[17] ^ s4_c0_17;
    assign s4_c0_18       = (A[17] & B[17]) | (A[17] & s4_c0_17) | (B[17] & s4_c0_17);
    assign sum0_stage4[18] = A[18] ^ B[18] ^ s4_c0_18;
    assign s4_c0_19       = (A[18] & B[18]) | (A[18] & s4_c0_18) | (B[18] & s4_c0_18);
    assign sum0_stage4[19] = A[19] ^ B[19] ^ s4_c0_19;
    assign s4_c0_20       = (A[19] & B[19]) | (A[19] & s4_c0_19) | (B[19] & s4_c0_19);
    assign sum0_stage4[20] = A[20] ^ B[20] ^ s4_c0_20;
    assign carry0_stage4 = (A[20] & B[20]) | (A[20] & s4_c0_20) | (B[20] & s4_c0_20);

    assign s4_c1_17       = 1'b1;
    assign sum1_stage4[17] = A[17] ^ B[17] ^ s4_c1_17;
    assign s4_c1_18       = (A[17] & B[17]) | (A[17] & s4_c1_17) | (B[17] & s4_c1_17);
    assign sum1_stage4[18] = A[18] ^ B[18] ^ s4_c1_18;
    assign s4_c1_19       = (A[18] & B[18]) | (A[18] & s4_c1_18) | (B[18] & s4_c1_18);
    assign sum1_stage4[19] = A[19] ^ B[19] ^ s4_c1_19;
    assign s4_c1_20       = (A[19] & B[19]) | (A[19] & s4_c1_19) | (B[19] & s4_c1_19);
    assign sum1_stage4[20] = A[20] ^ B[20] ^ s4_c1_20;
    assign carry1_stage4 = (A[20] & B[20]) | (A[20] & s4_c1_20) | (B[20] & s4_c1_20);

    assign select_stage4 = carry_stage3_selected;

    assign sum_int[17] = select_stage4 ? sum1_stage4[17] : sum0_stage4[17];
    assign sum_int[18] = select_stage4 ? sum1_stage4[18] : sum0_stage4[18];
    assign sum_int[19] = select_stage4 ? sum1_stage4[19] : sum0_stage4[19];
    assign sum_int[20] = select_stage4 ? sum1_stage4[20] : sum0_stage4[20];

    assign cout = select_stage4 ? carry1_stage4 : carry0_stage4;

endmodule
