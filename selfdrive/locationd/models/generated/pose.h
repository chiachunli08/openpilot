#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_err_fun(double *nom_x, double *delta_x, double *out_908811316603708218);
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_6097135032344727242);
void pose_H_mod_fun(double *state, double *out_5840907614347766849);
void pose_f_fun(double *state, double dt, double *out_6742419823108127014);
void pose_F_fun(double *state, double dt, double *out_7663122633241286867);
void pose_h_4(double *state, double *unused, double *out_7389052167092190980);
void pose_H_4(double *state, double *unused, double *out_7038855096230664953);
void pose_h_10(double *state, double *unused, double *out_8071536081821918077);
void pose_H_10(double *state, double *unused, double *out_4101630430643064156);
void pose_h_13(double *state, double *unused, double *out_4611633119501949975);
void pose_H_13(double *state, double *unused, double *out_8195615152146553862);
void pose_h_14(double *state, double *unused, double *out_519391538095944063);
void pose_H_14(double *state, double *unused, double *out_3956066663935292657);
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt);
}