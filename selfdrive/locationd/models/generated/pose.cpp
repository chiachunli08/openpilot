#include "pose.h"

namespace {
#define DIM 18
#define EDIM 18
#define MEDIM 18
typedef void (*Hfun)(double *, double *, double *);
const static double MAHA_THRESH_4 = 7.814727903251177;
const static double MAHA_THRESH_10 = 7.814727903251177;
const static double MAHA_THRESH_13 = 7.814727903251177;
const static double MAHA_THRESH_14 = 7.814727903251177;

/******************************************************************************
 *                      Code generated with SymPy 1.14.0                      *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_908811316603708218) {
   out_908811316603708218[0] = delta_x[0] + nom_x[0];
   out_908811316603708218[1] = delta_x[1] + nom_x[1];
   out_908811316603708218[2] = delta_x[2] + nom_x[2];
   out_908811316603708218[3] = delta_x[3] + nom_x[3];
   out_908811316603708218[4] = delta_x[4] + nom_x[4];
   out_908811316603708218[5] = delta_x[5] + nom_x[5];
   out_908811316603708218[6] = delta_x[6] + nom_x[6];
   out_908811316603708218[7] = delta_x[7] + nom_x[7];
   out_908811316603708218[8] = delta_x[8] + nom_x[8];
   out_908811316603708218[9] = delta_x[9] + nom_x[9];
   out_908811316603708218[10] = delta_x[10] + nom_x[10];
   out_908811316603708218[11] = delta_x[11] + nom_x[11];
   out_908811316603708218[12] = delta_x[12] + nom_x[12];
   out_908811316603708218[13] = delta_x[13] + nom_x[13];
   out_908811316603708218[14] = delta_x[14] + nom_x[14];
   out_908811316603708218[15] = delta_x[15] + nom_x[15];
   out_908811316603708218[16] = delta_x[16] + nom_x[16];
   out_908811316603708218[17] = delta_x[17] + nom_x[17];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_6097135032344727242) {
   out_6097135032344727242[0] = -nom_x[0] + true_x[0];
   out_6097135032344727242[1] = -nom_x[1] + true_x[1];
   out_6097135032344727242[2] = -nom_x[2] + true_x[2];
   out_6097135032344727242[3] = -nom_x[3] + true_x[3];
   out_6097135032344727242[4] = -nom_x[4] + true_x[4];
   out_6097135032344727242[5] = -nom_x[5] + true_x[5];
   out_6097135032344727242[6] = -nom_x[6] + true_x[6];
   out_6097135032344727242[7] = -nom_x[7] + true_x[7];
   out_6097135032344727242[8] = -nom_x[8] + true_x[8];
   out_6097135032344727242[9] = -nom_x[9] + true_x[9];
   out_6097135032344727242[10] = -nom_x[10] + true_x[10];
   out_6097135032344727242[11] = -nom_x[11] + true_x[11];
   out_6097135032344727242[12] = -nom_x[12] + true_x[12];
   out_6097135032344727242[13] = -nom_x[13] + true_x[13];
   out_6097135032344727242[14] = -nom_x[14] + true_x[14];
   out_6097135032344727242[15] = -nom_x[15] + true_x[15];
   out_6097135032344727242[16] = -nom_x[16] + true_x[16];
   out_6097135032344727242[17] = -nom_x[17] + true_x[17];
}
void H_mod_fun(double *state, double *out_5840907614347766849) {
   out_5840907614347766849[0] = 1.0;
   out_5840907614347766849[1] = 0.0;
   out_5840907614347766849[2] = 0.0;
   out_5840907614347766849[3] = 0.0;
   out_5840907614347766849[4] = 0.0;
   out_5840907614347766849[5] = 0.0;
   out_5840907614347766849[6] = 0.0;
   out_5840907614347766849[7] = 0.0;
   out_5840907614347766849[8] = 0.0;
   out_5840907614347766849[9] = 0.0;
   out_5840907614347766849[10] = 0.0;
   out_5840907614347766849[11] = 0.0;
   out_5840907614347766849[12] = 0.0;
   out_5840907614347766849[13] = 0.0;
   out_5840907614347766849[14] = 0.0;
   out_5840907614347766849[15] = 0.0;
   out_5840907614347766849[16] = 0.0;
   out_5840907614347766849[17] = 0.0;
   out_5840907614347766849[18] = 0.0;
   out_5840907614347766849[19] = 1.0;
   out_5840907614347766849[20] = 0.0;
   out_5840907614347766849[21] = 0.0;
   out_5840907614347766849[22] = 0.0;
   out_5840907614347766849[23] = 0.0;
   out_5840907614347766849[24] = 0.0;
   out_5840907614347766849[25] = 0.0;
   out_5840907614347766849[26] = 0.0;
   out_5840907614347766849[27] = 0.0;
   out_5840907614347766849[28] = 0.0;
   out_5840907614347766849[29] = 0.0;
   out_5840907614347766849[30] = 0.0;
   out_5840907614347766849[31] = 0.0;
   out_5840907614347766849[32] = 0.0;
   out_5840907614347766849[33] = 0.0;
   out_5840907614347766849[34] = 0.0;
   out_5840907614347766849[35] = 0.0;
   out_5840907614347766849[36] = 0.0;
   out_5840907614347766849[37] = 0.0;
   out_5840907614347766849[38] = 1.0;
   out_5840907614347766849[39] = 0.0;
   out_5840907614347766849[40] = 0.0;
   out_5840907614347766849[41] = 0.0;
   out_5840907614347766849[42] = 0.0;
   out_5840907614347766849[43] = 0.0;
   out_5840907614347766849[44] = 0.0;
   out_5840907614347766849[45] = 0.0;
   out_5840907614347766849[46] = 0.0;
   out_5840907614347766849[47] = 0.0;
   out_5840907614347766849[48] = 0.0;
   out_5840907614347766849[49] = 0.0;
   out_5840907614347766849[50] = 0.0;
   out_5840907614347766849[51] = 0.0;
   out_5840907614347766849[52] = 0.0;
   out_5840907614347766849[53] = 0.0;
   out_5840907614347766849[54] = 0.0;
   out_5840907614347766849[55] = 0.0;
   out_5840907614347766849[56] = 0.0;
   out_5840907614347766849[57] = 1.0;
   out_5840907614347766849[58] = 0.0;
   out_5840907614347766849[59] = 0.0;
   out_5840907614347766849[60] = 0.0;
   out_5840907614347766849[61] = 0.0;
   out_5840907614347766849[62] = 0.0;
   out_5840907614347766849[63] = 0.0;
   out_5840907614347766849[64] = 0.0;
   out_5840907614347766849[65] = 0.0;
   out_5840907614347766849[66] = 0.0;
   out_5840907614347766849[67] = 0.0;
   out_5840907614347766849[68] = 0.0;
   out_5840907614347766849[69] = 0.0;
   out_5840907614347766849[70] = 0.0;
   out_5840907614347766849[71] = 0.0;
   out_5840907614347766849[72] = 0.0;
   out_5840907614347766849[73] = 0.0;
   out_5840907614347766849[74] = 0.0;
   out_5840907614347766849[75] = 0.0;
   out_5840907614347766849[76] = 1.0;
   out_5840907614347766849[77] = 0.0;
   out_5840907614347766849[78] = 0.0;
   out_5840907614347766849[79] = 0.0;
   out_5840907614347766849[80] = 0.0;
   out_5840907614347766849[81] = 0.0;
   out_5840907614347766849[82] = 0.0;
   out_5840907614347766849[83] = 0.0;
   out_5840907614347766849[84] = 0.0;
   out_5840907614347766849[85] = 0.0;
   out_5840907614347766849[86] = 0.0;
   out_5840907614347766849[87] = 0.0;
   out_5840907614347766849[88] = 0.0;
   out_5840907614347766849[89] = 0.0;
   out_5840907614347766849[90] = 0.0;
   out_5840907614347766849[91] = 0.0;
   out_5840907614347766849[92] = 0.0;
   out_5840907614347766849[93] = 0.0;
   out_5840907614347766849[94] = 0.0;
   out_5840907614347766849[95] = 1.0;
   out_5840907614347766849[96] = 0.0;
   out_5840907614347766849[97] = 0.0;
   out_5840907614347766849[98] = 0.0;
   out_5840907614347766849[99] = 0.0;
   out_5840907614347766849[100] = 0.0;
   out_5840907614347766849[101] = 0.0;
   out_5840907614347766849[102] = 0.0;
   out_5840907614347766849[103] = 0.0;
   out_5840907614347766849[104] = 0.0;
   out_5840907614347766849[105] = 0.0;
   out_5840907614347766849[106] = 0.0;
   out_5840907614347766849[107] = 0.0;
   out_5840907614347766849[108] = 0.0;
   out_5840907614347766849[109] = 0.0;
   out_5840907614347766849[110] = 0.0;
   out_5840907614347766849[111] = 0.0;
   out_5840907614347766849[112] = 0.0;
   out_5840907614347766849[113] = 0.0;
   out_5840907614347766849[114] = 1.0;
   out_5840907614347766849[115] = 0.0;
   out_5840907614347766849[116] = 0.0;
   out_5840907614347766849[117] = 0.0;
   out_5840907614347766849[118] = 0.0;
   out_5840907614347766849[119] = 0.0;
   out_5840907614347766849[120] = 0.0;
   out_5840907614347766849[121] = 0.0;
   out_5840907614347766849[122] = 0.0;
   out_5840907614347766849[123] = 0.0;
   out_5840907614347766849[124] = 0.0;
   out_5840907614347766849[125] = 0.0;
   out_5840907614347766849[126] = 0.0;
   out_5840907614347766849[127] = 0.0;
   out_5840907614347766849[128] = 0.0;
   out_5840907614347766849[129] = 0.0;
   out_5840907614347766849[130] = 0.0;
   out_5840907614347766849[131] = 0.0;
   out_5840907614347766849[132] = 0.0;
   out_5840907614347766849[133] = 1.0;
   out_5840907614347766849[134] = 0.0;
   out_5840907614347766849[135] = 0.0;
   out_5840907614347766849[136] = 0.0;
   out_5840907614347766849[137] = 0.0;
   out_5840907614347766849[138] = 0.0;
   out_5840907614347766849[139] = 0.0;
   out_5840907614347766849[140] = 0.0;
   out_5840907614347766849[141] = 0.0;
   out_5840907614347766849[142] = 0.0;
   out_5840907614347766849[143] = 0.0;
   out_5840907614347766849[144] = 0.0;
   out_5840907614347766849[145] = 0.0;
   out_5840907614347766849[146] = 0.0;
   out_5840907614347766849[147] = 0.0;
   out_5840907614347766849[148] = 0.0;
   out_5840907614347766849[149] = 0.0;
   out_5840907614347766849[150] = 0.0;
   out_5840907614347766849[151] = 0.0;
   out_5840907614347766849[152] = 1.0;
   out_5840907614347766849[153] = 0.0;
   out_5840907614347766849[154] = 0.0;
   out_5840907614347766849[155] = 0.0;
   out_5840907614347766849[156] = 0.0;
   out_5840907614347766849[157] = 0.0;
   out_5840907614347766849[158] = 0.0;
   out_5840907614347766849[159] = 0.0;
   out_5840907614347766849[160] = 0.0;
   out_5840907614347766849[161] = 0.0;
   out_5840907614347766849[162] = 0.0;
   out_5840907614347766849[163] = 0.0;
   out_5840907614347766849[164] = 0.0;
   out_5840907614347766849[165] = 0.0;
   out_5840907614347766849[166] = 0.0;
   out_5840907614347766849[167] = 0.0;
   out_5840907614347766849[168] = 0.0;
   out_5840907614347766849[169] = 0.0;
   out_5840907614347766849[170] = 0.0;
   out_5840907614347766849[171] = 1.0;
   out_5840907614347766849[172] = 0.0;
   out_5840907614347766849[173] = 0.0;
   out_5840907614347766849[174] = 0.0;
   out_5840907614347766849[175] = 0.0;
   out_5840907614347766849[176] = 0.0;
   out_5840907614347766849[177] = 0.0;
   out_5840907614347766849[178] = 0.0;
   out_5840907614347766849[179] = 0.0;
   out_5840907614347766849[180] = 0.0;
   out_5840907614347766849[181] = 0.0;
   out_5840907614347766849[182] = 0.0;
   out_5840907614347766849[183] = 0.0;
   out_5840907614347766849[184] = 0.0;
   out_5840907614347766849[185] = 0.0;
   out_5840907614347766849[186] = 0.0;
   out_5840907614347766849[187] = 0.0;
   out_5840907614347766849[188] = 0.0;
   out_5840907614347766849[189] = 0.0;
   out_5840907614347766849[190] = 1.0;
   out_5840907614347766849[191] = 0.0;
   out_5840907614347766849[192] = 0.0;
   out_5840907614347766849[193] = 0.0;
   out_5840907614347766849[194] = 0.0;
   out_5840907614347766849[195] = 0.0;
   out_5840907614347766849[196] = 0.0;
   out_5840907614347766849[197] = 0.0;
   out_5840907614347766849[198] = 0.0;
   out_5840907614347766849[199] = 0.0;
   out_5840907614347766849[200] = 0.0;
   out_5840907614347766849[201] = 0.0;
   out_5840907614347766849[202] = 0.0;
   out_5840907614347766849[203] = 0.0;
   out_5840907614347766849[204] = 0.0;
   out_5840907614347766849[205] = 0.0;
   out_5840907614347766849[206] = 0.0;
   out_5840907614347766849[207] = 0.0;
   out_5840907614347766849[208] = 0.0;
   out_5840907614347766849[209] = 1.0;
   out_5840907614347766849[210] = 0.0;
   out_5840907614347766849[211] = 0.0;
   out_5840907614347766849[212] = 0.0;
   out_5840907614347766849[213] = 0.0;
   out_5840907614347766849[214] = 0.0;
   out_5840907614347766849[215] = 0.0;
   out_5840907614347766849[216] = 0.0;
   out_5840907614347766849[217] = 0.0;
   out_5840907614347766849[218] = 0.0;
   out_5840907614347766849[219] = 0.0;
   out_5840907614347766849[220] = 0.0;
   out_5840907614347766849[221] = 0.0;
   out_5840907614347766849[222] = 0.0;
   out_5840907614347766849[223] = 0.0;
   out_5840907614347766849[224] = 0.0;
   out_5840907614347766849[225] = 0.0;
   out_5840907614347766849[226] = 0.0;
   out_5840907614347766849[227] = 0.0;
   out_5840907614347766849[228] = 1.0;
   out_5840907614347766849[229] = 0.0;
   out_5840907614347766849[230] = 0.0;
   out_5840907614347766849[231] = 0.0;
   out_5840907614347766849[232] = 0.0;
   out_5840907614347766849[233] = 0.0;
   out_5840907614347766849[234] = 0.0;
   out_5840907614347766849[235] = 0.0;
   out_5840907614347766849[236] = 0.0;
   out_5840907614347766849[237] = 0.0;
   out_5840907614347766849[238] = 0.0;
   out_5840907614347766849[239] = 0.0;
   out_5840907614347766849[240] = 0.0;
   out_5840907614347766849[241] = 0.0;
   out_5840907614347766849[242] = 0.0;
   out_5840907614347766849[243] = 0.0;
   out_5840907614347766849[244] = 0.0;
   out_5840907614347766849[245] = 0.0;
   out_5840907614347766849[246] = 0.0;
   out_5840907614347766849[247] = 1.0;
   out_5840907614347766849[248] = 0.0;
   out_5840907614347766849[249] = 0.0;
   out_5840907614347766849[250] = 0.0;
   out_5840907614347766849[251] = 0.0;
   out_5840907614347766849[252] = 0.0;
   out_5840907614347766849[253] = 0.0;
   out_5840907614347766849[254] = 0.0;
   out_5840907614347766849[255] = 0.0;
   out_5840907614347766849[256] = 0.0;
   out_5840907614347766849[257] = 0.0;
   out_5840907614347766849[258] = 0.0;
   out_5840907614347766849[259] = 0.0;
   out_5840907614347766849[260] = 0.0;
   out_5840907614347766849[261] = 0.0;
   out_5840907614347766849[262] = 0.0;
   out_5840907614347766849[263] = 0.0;
   out_5840907614347766849[264] = 0.0;
   out_5840907614347766849[265] = 0.0;
   out_5840907614347766849[266] = 1.0;
   out_5840907614347766849[267] = 0.0;
   out_5840907614347766849[268] = 0.0;
   out_5840907614347766849[269] = 0.0;
   out_5840907614347766849[270] = 0.0;
   out_5840907614347766849[271] = 0.0;
   out_5840907614347766849[272] = 0.0;
   out_5840907614347766849[273] = 0.0;
   out_5840907614347766849[274] = 0.0;
   out_5840907614347766849[275] = 0.0;
   out_5840907614347766849[276] = 0.0;
   out_5840907614347766849[277] = 0.0;
   out_5840907614347766849[278] = 0.0;
   out_5840907614347766849[279] = 0.0;
   out_5840907614347766849[280] = 0.0;
   out_5840907614347766849[281] = 0.0;
   out_5840907614347766849[282] = 0.0;
   out_5840907614347766849[283] = 0.0;
   out_5840907614347766849[284] = 0.0;
   out_5840907614347766849[285] = 1.0;
   out_5840907614347766849[286] = 0.0;
   out_5840907614347766849[287] = 0.0;
   out_5840907614347766849[288] = 0.0;
   out_5840907614347766849[289] = 0.0;
   out_5840907614347766849[290] = 0.0;
   out_5840907614347766849[291] = 0.0;
   out_5840907614347766849[292] = 0.0;
   out_5840907614347766849[293] = 0.0;
   out_5840907614347766849[294] = 0.0;
   out_5840907614347766849[295] = 0.0;
   out_5840907614347766849[296] = 0.0;
   out_5840907614347766849[297] = 0.0;
   out_5840907614347766849[298] = 0.0;
   out_5840907614347766849[299] = 0.0;
   out_5840907614347766849[300] = 0.0;
   out_5840907614347766849[301] = 0.0;
   out_5840907614347766849[302] = 0.0;
   out_5840907614347766849[303] = 0.0;
   out_5840907614347766849[304] = 1.0;
   out_5840907614347766849[305] = 0.0;
   out_5840907614347766849[306] = 0.0;
   out_5840907614347766849[307] = 0.0;
   out_5840907614347766849[308] = 0.0;
   out_5840907614347766849[309] = 0.0;
   out_5840907614347766849[310] = 0.0;
   out_5840907614347766849[311] = 0.0;
   out_5840907614347766849[312] = 0.0;
   out_5840907614347766849[313] = 0.0;
   out_5840907614347766849[314] = 0.0;
   out_5840907614347766849[315] = 0.0;
   out_5840907614347766849[316] = 0.0;
   out_5840907614347766849[317] = 0.0;
   out_5840907614347766849[318] = 0.0;
   out_5840907614347766849[319] = 0.0;
   out_5840907614347766849[320] = 0.0;
   out_5840907614347766849[321] = 0.0;
   out_5840907614347766849[322] = 0.0;
   out_5840907614347766849[323] = 1.0;
}
void f_fun(double *state, double dt, double *out_6742419823108127014) {
   out_6742419823108127014[0] = atan2((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), -(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]));
   out_6742419823108127014[1] = asin(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]));
   out_6742419823108127014[2] = atan2(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), -(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]));
   out_6742419823108127014[3] = dt*state[12] + state[3];
   out_6742419823108127014[4] = dt*state[13] + state[4];
   out_6742419823108127014[5] = dt*state[14] + state[5];
   out_6742419823108127014[6] = state[6];
   out_6742419823108127014[7] = state[7];
   out_6742419823108127014[8] = state[8];
   out_6742419823108127014[9] = state[9];
   out_6742419823108127014[10] = state[10];
   out_6742419823108127014[11] = state[11];
   out_6742419823108127014[12] = state[12];
   out_6742419823108127014[13] = state[13];
   out_6742419823108127014[14] = state[14];
   out_6742419823108127014[15] = state[15];
   out_6742419823108127014[16] = state[16];
   out_6742419823108127014[17] = state[17];
}
void F_fun(double *state, double dt, double *out_7663122633241286867) {
   out_7663122633241286867[0] = ((-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*cos(state[0])*cos(state[1]) - sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*cos(state[0])*cos(state[1]) - sin(dt*state[6])*sin(state[0])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7663122633241286867[1] = ((-sin(dt*state[6])*sin(dt*state[8]) - sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*cos(state[1]) - (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*sin(state[1]) - sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(state[0]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*sin(state[1]) + (-sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) + sin(dt*state[8])*cos(dt*state[6]))*cos(state[1]) - sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(state[0]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7663122633241286867[2] = 0;
   out_7663122633241286867[3] = 0;
   out_7663122633241286867[4] = 0;
   out_7663122633241286867[5] = 0;
   out_7663122633241286867[6] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(dt*cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) - dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7663122633241286867[7] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*sin(dt*state[7])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[6])*sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) - dt*sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[7])*cos(dt*state[6])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[8])*sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]) - dt*sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7663122633241286867[8] = ((dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((dt*sin(dt*state[6])*sin(dt*state[8]) + dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7663122633241286867[9] = 0;
   out_7663122633241286867[10] = 0;
   out_7663122633241286867[11] = 0;
   out_7663122633241286867[12] = 0;
   out_7663122633241286867[13] = 0;
   out_7663122633241286867[14] = 0;
   out_7663122633241286867[15] = 0;
   out_7663122633241286867[16] = 0;
   out_7663122633241286867[17] = 0;
   out_7663122633241286867[18] = (-sin(dt*state[7])*sin(state[0])*cos(state[1]) - sin(dt*state[8])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7663122633241286867[19] = (-sin(dt*state[7])*sin(state[1])*cos(state[0]) + sin(dt*state[8])*sin(state[0])*sin(state[1])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7663122633241286867[20] = 0;
   out_7663122633241286867[21] = 0;
   out_7663122633241286867[22] = 0;
   out_7663122633241286867[23] = 0;
   out_7663122633241286867[24] = 0;
   out_7663122633241286867[25] = (dt*sin(dt*state[7])*sin(dt*state[8])*sin(state[0])*cos(state[1]) - dt*sin(dt*state[7])*sin(state[1])*cos(dt*state[8]) + dt*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7663122633241286867[26] = (-dt*sin(dt*state[8])*sin(state[1])*cos(dt*state[7]) - dt*sin(state[0])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7663122633241286867[27] = 0;
   out_7663122633241286867[28] = 0;
   out_7663122633241286867[29] = 0;
   out_7663122633241286867[30] = 0;
   out_7663122633241286867[31] = 0;
   out_7663122633241286867[32] = 0;
   out_7663122633241286867[33] = 0;
   out_7663122633241286867[34] = 0;
   out_7663122633241286867[35] = 0;
   out_7663122633241286867[36] = ((sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7663122633241286867[37] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-sin(dt*state[7])*sin(state[2])*cos(state[0])*cos(state[1]) + sin(dt*state[8])*sin(state[0])*sin(state[2])*cos(dt*state[7])*cos(state[1]) - sin(state[1])*sin(state[2])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(-sin(dt*state[7])*cos(state[0])*cos(state[1])*cos(state[2]) + sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1])*cos(state[2]) - sin(state[1])*cos(dt*state[7])*cos(dt*state[8])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7663122633241286867[38] = ((-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (-sin(state[0])*sin(state[1])*sin(state[2]) - cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7663122633241286867[39] = 0;
   out_7663122633241286867[40] = 0;
   out_7663122633241286867[41] = 0;
   out_7663122633241286867[42] = 0;
   out_7663122633241286867[43] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(dt*(sin(state[0])*cos(state[2]) - sin(state[1])*sin(state[2])*cos(state[0]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*sin(state[2])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(dt*(-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7663122633241286867[44] = (dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*sin(state[2])*cos(dt*state[7])*cos(state[1]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + (dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[7])*cos(state[1])*cos(state[2]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7663122633241286867[45] = 0;
   out_7663122633241286867[46] = 0;
   out_7663122633241286867[47] = 0;
   out_7663122633241286867[48] = 0;
   out_7663122633241286867[49] = 0;
   out_7663122633241286867[50] = 0;
   out_7663122633241286867[51] = 0;
   out_7663122633241286867[52] = 0;
   out_7663122633241286867[53] = 0;
   out_7663122633241286867[54] = 0;
   out_7663122633241286867[55] = 0;
   out_7663122633241286867[56] = 0;
   out_7663122633241286867[57] = 1;
   out_7663122633241286867[58] = 0;
   out_7663122633241286867[59] = 0;
   out_7663122633241286867[60] = 0;
   out_7663122633241286867[61] = 0;
   out_7663122633241286867[62] = 0;
   out_7663122633241286867[63] = 0;
   out_7663122633241286867[64] = 0;
   out_7663122633241286867[65] = 0;
   out_7663122633241286867[66] = dt;
   out_7663122633241286867[67] = 0;
   out_7663122633241286867[68] = 0;
   out_7663122633241286867[69] = 0;
   out_7663122633241286867[70] = 0;
   out_7663122633241286867[71] = 0;
   out_7663122633241286867[72] = 0;
   out_7663122633241286867[73] = 0;
   out_7663122633241286867[74] = 0;
   out_7663122633241286867[75] = 0;
   out_7663122633241286867[76] = 1;
   out_7663122633241286867[77] = 0;
   out_7663122633241286867[78] = 0;
   out_7663122633241286867[79] = 0;
   out_7663122633241286867[80] = 0;
   out_7663122633241286867[81] = 0;
   out_7663122633241286867[82] = 0;
   out_7663122633241286867[83] = 0;
   out_7663122633241286867[84] = 0;
   out_7663122633241286867[85] = dt;
   out_7663122633241286867[86] = 0;
   out_7663122633241286867[87] = 0;
   out_7663122633241286867[88] = 0;
   out_7663122633241286867[89] = 0;
   out_7663122633241286867[90] = 0;
   out_7663122633241286867[91] = 0;
   out_7663122633241286867[92] = 0;
   out_7663122633241286867[93] = 0;
   out_7663122633241286867[94] = 0;
   out_7663122633241286867[95] = 1;
   out_7663122633241286867[96] = 0;
   out_7663122633241286867[97] = 0;
   out_7663122633241286867[98] = 0;
   out_7663122633241286867[99] = 0;
   out_7663122633241286867[100] = 0;
   out_7663122633241286867[101] = 0;
   out_7663122633241286867[102] = 0;
   out_7663122633241286867[103] = 0;
   out_7663122633241286867[104] = dt;
   out_7663122633241286867[105] = 0;
   out_7663122633241286867[106] = 0;
   out_7663122633241286867[107] = 0;
   out_7663122633241286867[108] = 0;
   out_7663122633241286867[109] = 0;
   out_7663122633241286867[110] = 0;
   out_7663122633241286867[111] = 0;
   out_7663122633241286867[112] = 0;
   out_7663122633241286867[113] = 0;
   out_7663122633241286867[114] = 1;
   out_7663122633241286867[115] = 0;
   out_7663122633241286867[116] = 0;
   out_7663122633241286867[117] = 0;
   out_7663122633241286867[118] = 0;
   out_7663122633241286867[119] = 0;
   out_7663122633241286867[120] = 0;
   out_7663122633241286867[121] = 0;
   out_7663122633241286867[122] = 0;
   out_7663122633241286867[123] = 0;
   out_7663122633241286867[124] = 0;
   out_7663122633241286867[125] = 0;
   out_7663122633241286867[126] = 0;
   out_7663122633241286867[127] = 0;
   out_7663122633241286867[128] = 0;
   out_7663122633241286867[129] = 0;
   out_7663122633241286867[130] = 0;
   out_7663122633241286867[131] = 0;
   out_7663122633241286867[132] = 0;
   out_7663122633241286867[133] = 1;
   out_7663122633241286867[134] = 0;
   out_7663122633241286867[135] = 0;
   out_7663122633241286867[136] = 0;
   out_7663122633241286867[137] = 0;
   out_7663122633241286867[138] = 0;
   out_7663122633241286867[139] = 0;
   out_7663122633241286867[140] = 0;
   out_7663122633241286867[141] = 0;
   out_7663122633241286867[142] = 0;
   out_7663122633241286867[143] = 0;
   out_7663122633241286867[144] = 0;
   out_7663122633241286867[145] = 0;
   out_7663122633241286867[146] = 0;
   out_7663122633241286867[147] = 0;
   out_7663122633241286867[148] = 0;
   out_7663122633241286867[149] = 0;
   out_7663122633241286867[150] = 0;
   out_7663122633241286867[151] = 0;
   out_7663122633241286867[152] = 1;
   out_7663122633241286867[153] = 0;
   out_7663122633241286867[154] = 0;
   out_7663122633241286867[155] = 0;
   out_7663122633241286867[156] = 0;
   out_7663122633241286867[157] = 0;
   out_7663122633241286867[158] = 0;
   out_7663122633241286867[159] = 0;
   out_7663122633241286867[160] = 0;
   out_7663122633241286867[161] = 0;
   out_7663122633241286867[162] = 0;
   out_7663122633241286867[163] = 0;
   out_7663122633241286867[164] = 0;
   out_7663122633241286867[165] = 0;
   out_7663122633241286867[166] = 0;
   out_7663122633241286867[167] = 0;
   out_7663122633241286867[168] = 0;
   out_7663122633241286867[169] = 0;
   out_7663122633241286867[170] = 0;
   out_7663122633241286867[171] = 1;
   out_7663122633241286867[172] = 0;
   out_7663122633241286867[173] = 0;
   out_7663122633241286867[174] = 0;
   out_7663122633241286867[175] = 0;
   out_7663122633241286867[176] = 0;
   out_7663122633241286867[177] = 0;
   out_7663122633241286867[178] = 0;
   out_7663122633241286867[179] = 0;
   out_7663122633241286867[180] = 0;
   out_7663122633241286867[181] = 0;
   out_7663122633241286867[182] = 0;
   out_7663122633241286867[183] = 0;
   out_7663122633241286867[184] = 0;
   out_7663122633241286867[185] = 0;
   out_7663122633241286867[186] = 0;
   out_7663122633241286867[187] = 0;
   out_7663122633241286867[188] = 0;
   out_7663122633241286867[189] = 0;
   out_7663122633241286867[190] = 1;
   out_7663122633241286867[191] = 0;
   out_7663122633241286867[192] = 0;
   out_7663122633241286867[193] = 0;
   out_7663122633241286867[194] = 0;
   out_7663122633241286867[195] = 0;
   out_7663122633241286867[196] = 0;
   out_7663122633241286867[197] = 0;
   out_7663122633241286867[198] = 0;
   out_7663122633241286867[199] = 0;
   out_7663122633241286867[200] = 0;
   out_7663122633241286867[201] = 0;
   out_7663122633241286867[202] = 0;
   out_7663122633241286867[203] = 0;
   out_7663122633241286867[204] = 0;
   out_7663122633241286867[205] = 0;
   out_7663122633241286867[206] = 0;
   out_7663122633241286867[207] = 0;
   out_7663122633241286867[208] = 0;
   out_7663122633241286867[209] = 1;
   out_7663122633241286867[210] = 0;
   out_7663122633241286867[211] = 0;
   out_7663122633241286867[212] = 0;
   out_7663122633241286867[213] = 0;
   out_7663122633241286867[214] = 0;
   out_7663122633241286867[215] = 0;
   out_7663122633241286867[216] = 0;
   out_7663122633241286867[217] = 0;
   out_7663122633241286867[218] = 0;
   out_7663122633241286867[219] = 0;
   out_7663122633241286867[220] = 0;
   out_7663122633241286867[221] = 0;
   out_7663122633241286867[222] = 0;
   out_7663122633241286867[223] = 0;
   out_7663122633241286867[224] = 0;
   out_7663122633241286867[225] = 0;
   out_7663122633241286867[226] = 0;
   out_7663122633241286867[227] = 0;
   out_7663122633241286867[228] = 1;
   out_7663122633241286867[229] = 0;
   out_7663122633241286867[230] = 0;
   out_7663122633241286867[231] = 0;
   out_7663122633241286867[232] = 0;
   out_7663122633241286867[233] = 0;
   out_7663122633241286867[234] = 0;
   out_7663122633241286867[235] = 0;
   out_7663122633241286867[236] = 0;
   out_7663122633241286867[237] = 0;
   out_7663122633241286867[238] = 0;
   out_7663122633241286867[239] = 0;
   out_7663122633241286867[240] = 0;
   out_7663122633241286867[241] = 0;
   out_7663122633241286867[242] = 0;
   out_7663122633241286867[243] = 0;
   out_7663122633241286867[244] = 0;
   out_7663122633241286867[245] = 0;
   out_7663122633241286867[246] = 0;
   out_7663122633241286867[247] = 1;
   out_7663122633241286867[248] = 0;
   out_7663122633241286867[249] = 0;
   out_7663122633241286867[250] = 0;
   out_7663122633241286867[251] = 0;
   out_7663122633241286867[252] = 0;
   out_7663122633241286867[253] = 0;
   out_7663122633241286867[254] = 0;
   out_7663122633241286867[255] = 0;
   out_7663122633241286867[256] = 0;
   out_7663122633241286867[257] = 0;
   out_7663122633241286867[258] = 0;
   out_7663122633241286867[259] = 0;
   out_7663122633241286867[260] = 0;
   out_7663122633241286867[261] = 0;
   out_7663122633241286867[262] = 0;
   out_7663122633241286867[263] = 0;
   out_7663122633241286867[264] = 0;
   out_7663122633241286867[265] = 0;
   out_7663122633241286867[266] = 1;
   out_7663122633241286867[267] = 0;
   out_7663122633241286867[268] = 0;
   out_7663122633241286867[269] = 0;
   out_7663122633241286867[270] = 0;
   out_7663122633241286867[271] = 0;
   out_7663122633241286867[272] = 0;
   out_7663122633241286867[273] = 0;
   out_7663122633241286867[274] = 0;
   out_7663122633241286867[275] = 0;
   out_7663122633241286867[276] = 0;
   out_7663122633241286867[277] = 0;
   out_7663122633241286867[278] = 0;
   out_7663122633241286867[279] = 0;
   out_7663122633241286867[280] = 0;
   out_7663122633241286867[281] = 0;
   out_7663122633241286867[282] = 0;
   out_7663122633241286867[283] = 0;
   out_7663122633241286867[284] = 0;
   out_7663122633241286867[285] = 1;
   out_7663122633241286867[286] = 0;
   out_7663122633241286867[287] = 0;
   out_7663122633241286867[288] = 0;
   out_7663122633241286867[289] = 0;
   out_7663122633241286867[290] = 0;
   out_7663122633241286867[291] = 0;
   out_7663122633241286867[292] = 0;
   out_7663122633241286867[293] = 0;
   out_7663122633241286867[294] = 0;
   out_7663122633241286867[295] = 0;
   out_7663122633241286867[296] = 0;
   out_7663122633241286867[297] = 0;
   out_7663122633241286867[298] = 0;
   out_7663122633241286867[299] = 0;
   out_7663122633241286867[300] = 0;
   out_7663122633241286867[301] = 0;
   out_7663122633241286867[302] = 0;
   out_7663122633241286867[303] = 0;
   out_7663122633241286867[304] = 1;
   out_7663122633241286867[305] = 0;
   out_7663122633241286867[306] = 0;
   out_7663122633241286867[307] = 0;
   out_7663122633241286867[308] = 0;
   out_7663122633241286867[309] = 0;
   out_7663122633241286867[310] = 0;
   out_7663122633241286867[311] = 0;
   out_7663122633241286867[312] = 0;
   out_7663122633241286867[313] = 0;
   out_7663122633241286867[314] = 0;
   out_7663122633241286867[315] = 0;
   out_7663122633241286867[316] = 0;
   out_7663122633241286867[317] = 0;
   out_7663122633241286867[318] = 0;
   out_7663122633241286867[319] = 0;
   out_7663122633241286867[320] = 0;
   out_7663122633241286867[321] = 0;
   out_7663122633241286867[322] = 0;
   out_7663122633241286867[323] = 1;
}
void h_4(double *state, double *unused, double *out_7389052167092190980) {
   out_7389052167092190980[0] = state[6] + state[9];
   out_7389052167092190980[1] = state[7] + state[10];
   out_7389052167092190980[2] = state[8] + state[11];
}
void H_4(double *state, double *unused, double *out_7038855096230664953) {
   out_7038855096230664953[0] = 0;
   out_7038855096230664953[1] = 0;
   out_7038855096230664953[2] = 0;
   out_7038855096230664953[3] = 0;
   out_7038855096230664953[4] = 0;
   out_7038855096230664953[5] = 0;
   out_7038855096230664953[6] = 1;
   out_7038855096230664953[7] = 0;
   out_7038855096230664953[8] = 0;
   out_7038855096230664953[9] = 1;
   out_7038855096230664953[10] = 0;
   out_7038855096230664953[11] = 0;
   out_7038855096230664953[12] = 0;
   out_7038855096230664953[13] = 0;
   out_7038855096230664953[14] = 0;
   out_7038855096230664953[15] = 0;
   out_7038855096230664953[16] = 0;
   out_7038855096230664953[17] = 0;
   out_7038855096230664953[18] = 0;
   out_7038855096230664953[19] = 0;
   out_7038855096230664953[20] = 0;
   out_7038855096230664953[21] = 0;
   out_7038855096230664953[22] = 0;
   out_7038855096230664953[23] = 0;
   out_7038855096230664953[24] = 0;
   out_7038855096230664953[25] = 1;
   out_7038855096230664953[26] = 0;
   out_7038855096230664953[27] = 0;
   out_7038855096230664953[28] = 1;
   out_7038855096230664953[29] = 0;
   out_7038855096230664953[30] = 0;
   out_7038855096230664953[31] = 0;
   out_7038855096230664953[32] = 0;
   out_7038855096230664953[33] = 0;
   out_7038855096230664953[34] = 0;
   out_7038855096230664953[35] = 0;
   out_7038855096230664953[36] = 0;
   out_7038855096230664953[37] = 0;
   out_7038855096230664953[38] = 0;
   out_7038855096230664953[39] = 0;
   out_7038855096230664953[40] = 0;
   out_7038855096230664953[41] = 0;
   out_7038855096230664953[42] = 0;
   out_7038855096230664953[43] = 0;
   out_7038855096230664953[44] = 1;
   out_7038855096230664953[45] = 0;
   out_7038855096230664953[46] = 0;
   out_7038855096230664953[47] = 1;
   out_7038855096230664953[48] = 0;
   out_7038855096230664953[49] = 0;
   out_7038855096230664953[50] = 0;
   out_7038855096230664953[51] = 0;
   out_7038855096230664953[52] = 0;
   out_7038855096230664953[53] = 0;
}
void h_10(double *state, double *unused, double *out_8071536081821918077) {
   out_8071536081821918077[0] = 9.8100000000000005*sin(state[1]) - state[4]*state[8] + state[5]*state[7] + state[12] + state[15];
   out_8071536081821918077[1] = -9.8100000000000005*sin(state[0])*cos(state[1]) + state[3]*state[8] - state[5]*state[6] + state[13] + state[16];
   out_8071536081821918077[2] = -9.8100000000000005*cos(state[0])*cos(state[1]) - state[3]*state[7] + state[4]*state[6] + state[14] + state[17];
}
void H_10(double *state, double *unused, double *out_4101630430643064156) {
   out_4101630430643064156[0] = 0;
   out_4101630430643064156[1] = 9.8100000000000005*cos(state[1]);
   out_4101630430643064156[2] = 0;
   out_4101630430643064156[3] = 0;
   out_4101630430643064156[4] = -state[8];
   out_4101630430643064156[5] = state[7];
   out_4101630430643064156[6] = 0;
   out_4101630430643064156[7] = state[5];
   out_4101630430643064156[8] = -state[4];
   out_4101630430643064156[9] = 0;
   out_4101630430643064156[10] = 0;
   out_4101630430643064156[11] = 0;
   out_4101630430643064156[12] = 1;
   out_4101630430643064156[13] = 0;
   out_4101630430643064156[14] = 0;
   out_4101630430643064156[15] = 1;
   out_4101630430643064156[16] = 0;
   out_4101630430643064156[17] = 0;
   out_4101630430643064156[18] = -9.8100000000000005*cos(state[0])*cos(state[1]);
   out_4101630430643064156[19] = 9.8100000000000005*sin(state[0])*sin(state[1]);
   out_4101630430643064156[20] = 0;
   out_4101630430643064156[21] = state[8];
   out_4101630430643064156[22] = 0;
   out_4101630430643064156[23] = -state[6];
   out_4101630430643064156[24] = -state[5];
   out_4101630430643064156[25] = 0;
   out_4101630430643064156[26] = state[3];
   out_4101630430643064156[27] = 0;
   out_4101630430643064156[28] = 0;
   out_4101630430643064156[29] = 0;
   out_4101630430643064156[30] = 0;
   out_4101630430643064156[31] = 1;
   out_4101630430643064156[32] = 0;
   out_4101630430643064156[33] = 0;
   out_4101630430643064156[34] = 1;
   out_4101630430643064156[35] = 0;
   out_4101630430643064156[36] = 9.8100000000000005*sin(state[0])*cos(state[1]);
   out_4101630430643064156[37] = 9.8100000000000005*sin(state[1])*cos(state[0]);
   out_4101630430643064156[38] = 0;
   out_4101630430643064156[39] = -state[7];
   out_4101630430643064156[40] = state[6];
   out_4101630430643064156[41] = 0;
   out_4101630430643064156[42] = state[4];
   out_4101630430643064156[43] = -state[3];
   out_4101630430643064156[44] = 0;
   out_4101630430643064156[45] = 0;
   out_4101630430643064156[46] = 0;
   out_4101630430643064156[47] = 0;
   out_4101630430643064156[48] = 0;
   out_4101630430643064156[49] = 0;
   out_4101630430643064156[50] = 1;
   out_4101630430643064156[51] = 0;
   out_4101630430643064156[52] = 0;
   out_4101630430643064156[53] = 1;
}
void h_13(double *state, double *unused, double *out_4611633119501949975) {
   out_4611633119501949975[0] = state[3];
   out_4611633119501949975[1] = state[4];
   out_4611633119501949975[2] = state[5];
}
void H_13(double *state, double *unused, double *out_8195615152146553862) {
   out_8195615152146553862[0] = 0;
   out_8195615152146553862[1] = 0;
   out_8195615152146553862[2] = 0;
   out_8195615152146553862[3] = 1;
   out_8195615152146553862[4] = 0;
   out_8195615152146553862[5] = 0;
   out_8195615152146553862[6] = 0;
   out_8195615152146553862[7] = 0;
   out_8195615152146553862[8] = 0;
   out_8195615152146553862[9] = 0;
   out_8195615152146553862[10] = 0;
   out_8195615152146553862[11] = 0;
   out_8195615152146553862[12] = 0;
   out_8195615152146553862[13] = 0;
   out_8195615152146553862[14] = 0;
   out_8195615152146553862[15] = 0;
   out_8195615152146553862[16] = 0;
   out_8195615152146553862[17] = 0;
   out_8195615152146553862[18] = 0;
   out_8195615152146553862[19] = 0;
   out_8195615152146553862[20] = 0;
   out_8195615152146553862[21] = 0;
   out_8195615152146553862[22] = 1;
   out_8195615152146553862[23] = 0;
   out_8195615152146553862[24] = 0;
   out_8195615152146553862[25] = 0;
   out_8195615152146553862[26] = 0;
   out_8195615152146553862[27] = 0;
   out_8195615152146553862[28] = 0;
   out_8195615152146553862[29] = 0;
   out_8195615152146553862[30] = 0;
   out_8195615152146553862[31] = 0;
   out_8195615152146553862[32] = 0;
   out_8195615152146553862[33] = 0;
   out_8195615152146553862[34] = 0;
   out_8195615152146553862[35] = 0;
   out_8195615152146553862[36] = 0;
   out_8195615152146553862[37] = 0;
   out_8195615152146553862[38] = 0;
   out_8195615152146553862[39] = 0;
   out_8195615152146553862[40] = 0;
   out_8195615152146553862[41] = 1;
   out_8195615152146553862[42] = 0;
   out_8195615152146553862[43] = 0;
   out_8195615152146553862[44] = 0;
   out_8195615152146553862[45] = 0;
   out_8195615152146553862[46] = 0;
   out_8195615152146553862[47] = 0;
   out_8195615152146553862[48] = 0;
   out_8195615152146553862[49] = 0;
   out_8195615152146553862[50] = 0;
   out_8195615152146553862[51] = 0;
   out_8195615152146553862[52] = 0;
   out_8195615152146553862[53] = 0;
}
void h_14(double *state, double *unused, double *out_519391538095944063) {
   out_519391538095944063[0] = state[6];
   out_519391538095944063[1] = state[7];
   out_519391538095944063[2] = state[8];
}
void H_14(double *state, double *unused, double *out_3956066663935292657) {
   out_3956066663935292657[0] = 0;
   out_3956066663935292657[1] = 0;
   out_3956066663935292657[2] = 0;
   out_3956066663935292657[3] = 0;
   out_3956066663935292657[4] = 0;
   out_3956066663935292657[5] = 0;
   out_3956066663935292657[6] = 1;
   out_3956066663935292657[7] = 0;
   out_3956066663935292657[8] = 0;
   out_3956066663935292657[9] = 0;
   out_3956066663935292657[10] = 0;
   out_3956066663935292657[11] = 0;
   out_3956066663935292657[12] = 0;
   out_3956066663935292657[13] = 0;
   out_3956066663935292657[14] = 0;
   out_3956066663935292657[15] = 0;
   out_3956066663935292657[16] = 0;
   out_3956066663935292657[17] = 0;
   out_3956066663935292657[18] = 0;
   out_3956066663935292657[19] = 0;
   out_3956066663935292657[20] = 0;
   out_3956066663935292657[21] = 0;
   out_3956066663935292657[22] = 0;
   out_3956066663935292657[23] = 0;
   out_3956066663935292657[24] = 0;
   out_3956066663935292657[25] = 1;
   out_3956066663935292657[26] = 0;
   out_3956066663935292657[27] = 0;
   out_3956066663935292657[28] = 0;
   out_3956066663935292657[29] = 0;
   out_3956066663935292657[30] = 0;
   out_3956066663935292657[31] = 0;
   out_3956066663935292657[32] = 0;
   out_3956066663935292657[33] = 0;
   out_3956066663935292657[34] = 0;
   out_3956066663935292657[35] = 0;
   out_3956066663935292657[36] = 0;
   out_3956066663935292657[37] = 0;
   out_3956066663935292657[38] = 0;
   out_3956066663935292657[39] = 0;
   out_3956066663935292657[40] = 0;
   out_3956066663935292657[41] = 0;
   out_3956066663935292657[42] = 0;
   out_3956066663935292657[43] = 0;
   out_3956066663935292657[44] = 1;
   out_3956066663935292657[45] = 0;
   out_3956066663935292657[46] = 0;
   out_3956066663935292657[47] = 0;
   out_3956066663935292657[48] = 0;
   out_3956066663935292657[49] = 0;
   out_3956066663935292657[50] = 0;
   out_3956066663935292657[51] = 0;
   out_3956066663935292657[52] = 0;
   out_3956066663935292657[53] = 0;
}
#include <eigen3/Eigen/Dense>
#include <iostream>

typedef Eigen::Matrix<double, DIM, DIM, Eigen::RowMajor> DDM;
typedef Eigen::Matrix<double, EDIM, EDIM, Eigen::RowMajor> EEM;
typedef Eigen::Matrix<double, DIM, EDIM, Eigen::RowMajor> DEM;

void predict(double *in_x, double *in_P, double *in_Q, double dt) {
  typedef Eigen::Matrix<double, MEDIM, MEDIM, Eigen::RowMajor> RRM;

  double nx[DIM] = {0};
  double in_F[EDIM*EDIM] = {0};

  // functions from sympy
  f_fun(in_x, dt, nx);
  F_fun(in_x, dt, in_F);


  EEM F(in_F);
  EEM P(in_P);
  EEM Q(in_Q);

  RRM F_main = F.topLeftCorner(MEDIM, MEDIM);
  P.topLeftCorner(MEDIM, MEDIM) = (F_main * P.topLeftCorner(MEDIM, MEDIM)) * F_main.transpose();
  P.topRightCorner(MEDIM, EDIM - MEDIM) = F_main * P.topRightCorner(MEDIM, EDIM - MEDIM);
  P.bottomLeftCorner(EDIM - MEDIM, MEDIM) = P.bottomLeftCorner(EDIM - MEDIM, MEDIM) * F_main.transpose();

  P = P + dt*Q;

  // copy out state
  memcpy(in_x, nx, DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
}

// note: extra_args dim only correct when null space projecting
// otherwise 1
template <int ZDIM, int EADIM, bool MAHA_TEST>
void update(double *in_x, double *in_P, Hfun h_fun, Hfun H_fun, Hfun Hea_fun, double *in_z, double *in_R, double *in_ea, double MAHA_THRESHOLD) {
  typedef Eigen::Matrix<double, ZDIM, ZDIM, Eigen::RowMajor> ZZM;
  typedef Eigen::Matrix<double, ZDIM, DIM, Eigen::RowMajor> ZDM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, EDIM, Eigen::RowMajor> XEM;
  //typedef Eigen::Matrix<double, EDIM, ZDIM, Eigen::RowMajor> EZM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, 1> X1M;
  typedef Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor> XXM;

  double in_hx[ZDIM] = {0};
  double in_H[ZDIM * DIM] = {0};
  double in_H_mod[EDIM * DIM] = {0};
  double delta_x[EDIM] = {0};
  double x_new[DIM] = {0};


  // state x, P
  Eigen::Matrix<double, ZDIM, 1> z(in_z);
  EEM P(in_P);
  ZZM pre_R(in_R);

  // functions from sympy
  h_fun(in_x, in_ea, in_hx);
  H_fun(in_x, in_ea, in_H);
  ZDM pre_H(in_H);

  // get y (y = z - hx)
  Eigen::Matrix<double, ZDIM, 1> pre_y(in_hx); pre_y = z - pre_y;
  X1M y; XXM H; XXM R;
  if (Hea_fun){
    typedef Eigen::Matrix<double, ZDIM, EADIM, Eigen::RowMajor> ZAM;
    double in_Hea[ZDIM * EADIM] = {0};
    Hea_fun(in_x, in_ea, in_Hea);
    ZAM Hea(in_Hea);
    XXM A = Hea.transpose().fullPivLu().kernel();


    y = A.transpose() * pre_y;
    H = A.transpose() * pre_H;
    R = A.transpose() * pre_R * A;
  } else {
    y = pre_y;
    H = pre_H;
    R = pre_R;
  }
  // get modified H
  H_mod_fun(in_x, in_H_mod);
  DEM H_mod(in_H_mod);
  XEM H_err = H * H_mod;

  // Do mahalobis distance test
  if (MAHA_TEST){
    XXM a = (H_err * P * H_err.transpose() + R).inverse();
    double maha_dist = y.transpose() * a * y;
    if (maha_dist > MAHA_THRESHOLD){
      R = 1.0e16 * R;
    }
  }

  // Outlier resilient weighting
  double weight = 1;//(1.5)/(1 + y.squaredNorm()/R.sum());

  // kalman gains and I_KH
  XXM S = ((H_err * P) * H_err.transpose()) + R/weight;
  XEM KT = S.fullPivLu().solve(H_err * P.transpose());
  //EZM K = KT.transpose(); TODO: WHY DOES THIS NOT COMPILE?
  //EZM K = S.fullPivLu().solve(H_err * P.transpose()).transpose();
  //std::cout << "Here is the matrix rot:\n" << K << std::endl;
  EEM I_KH = Eigen::Matrix<double, EDIM, EDIM>::Identity() - (KT.transpose() * H_err);

  // update state by injecting dx
  Eigen::Matrix<double, EDIM, 1> dx(delta_x);
  dx  = (KT.transpose() * y);
  memcpy(delta_x, dx.data(), EDIM * sizeof(double));
  err_fun(in_x, delta_x, x_new);
  Eigen::Matrix<double, DIM, 1> x(x_new);

  // update cov
  P = ((I_KH * P) * I_KH.transpose()) + ((KT.transpose() * R) * KT);

  // copy out state
  memcpy(in_x, x.data(), DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
  memcpy(in_z, y.data(), y.rows() * sizeof(double));
}




}
extern "C" {

void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_4, H_4, NULL, in_z, in_R, in_ea, MAHA_THRESH_4);
}
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_10, H_10, NULL, in_z, in_R, in_ea, MAHA_THRESH_10);
}
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_13, H_13, NULL, in_z, in_R, in_ea, MAHA_THRESH_13);
}
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_14, H_14, NULL, in_z, in_R, in_ea, MAHA_THRESH_14);
}
void pose_err_fun(double *nom_x, double *delta_x, double *out_908811316603708218) {
  err_fun(nom_x, delta_x, out_908811316603708218);
}
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_6097135032344727242) {
  inv_err_fun(nom_x, true_x, out_6097135032344727242);
}
void pose_H_mod_fun(double *state, double *out_5840907614347766849) {
  H_mod_fun(state, out_5840907614347766849);
}
void pose_f_fun(double *state, double dt, double *out_6742419823108127014) {
  f_fun(state,  dt, out_6742419823108127014);
}
void pose_F_fun(double *state, double dt, double *out_7663122633241286867) {
  F_fun(state,  dt, out_7663122633241286867);
}
void pose_h_4(double *state, double *unused, double *out_7389052167092190980) {
  h_4(state, unused, out_7389052167092190980);
}
void pose_H_4(double *state, double *unused, double *out_7038855096230664953) {
  H_4(state, unused, out_7038855096230664953);
}
void pose_h_10(double *state, double *unused, double *out_8071536081821918077) {
  h_10(state, unused, out_8071536081821918077);
}
void pose_H_10(double *state, double *unused, double *out_4101630430643064156) {
  H_10(state, unused, out_4101630430643064156);
}
void pose_h_13(double *state, double *unused, double *out_4611633119501949975) {
  h_13(state, unused, out_4611633119501949975);
}
void pose_H_13(double *state, double *unused, double *out_8195615152146553862) {
  H_13(state, unused, out_8195615152146553862);
}
void pose_h_14(double *state, double *unused, double *out_519391538095944063) {
  h_14(state, unused, out_519391538095944063);
}
void pose_H_14(double *state, double *unused, double *out_3956066663935292657) {
  H_14(state, unused, out_3956066663935292657);
}
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
}

const EKF pose = {
  .name = "pose",
  .kinds = { 4, 10, 13, 14 },
  .feature_kinds = {  },
  .f_fun = pose_f_fun,
  .F_fun = pose_F_fun,
  .err_fun = pose_err_fun,
  .inv_err_fun = pose_inv_err_fun,
  .H_mod_fun = pose_H_mod_fun,
  .predict = pose_predict,
  .hs = {
    { 4, pose_h_4 },
    { 10, pose_h_10 },
    { 13, pose_h_13 },
    { 14, pose_h_14 },
  },
  .Hs = {
    { 4, pose_H_4 },
    { 10, pose_H_10 },
    { 13, pose_H_13 },
    { 14, pose_H_14 },
  },
  .updates = {
    { 4, pose_update_4 },
    { 10, pose_update_10 },
    { 13, pose_update_13 },
    { 14, pose_update_14 },
  },
  .Hes = {
  },
  .sets = {
  },
  .extra_routines = {
  },
};

ekf_lib_init(pose)
