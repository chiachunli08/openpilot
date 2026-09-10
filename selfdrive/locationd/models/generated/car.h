#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_err_fun(double *nom_x, double *delta_x, double *out_1264104166079454940);
void car_inv_err_fun(double *nom_x, double *true_x, double *out_3182169158929336617);
void car_H_mod_fun(double *state, double *out_3410660055109284948);
void car_f_fun(double *state, double dt, double *out_6946480961019455904);
void car_F_fun(double *state, double dt, double *out_2425315094814185050);
void car_h_25(double *state, double *unused, double *out_3083351420745802205);
void car_H_25(double *state, double *unused, double *out_1342134769348572192);
void car_h_24(double *state, double *unused, double *out_7968288456028556638);
void car_H_24(double *state, double *unused, double *out_7917706575940090293);
void car_h_30(double *state, double *unused, double *out_8592557426613398475);
void car_H_30(double *state, double *unused, double *out_8258825110840188947);
void car_h_26(double *state, double *unused, double *out_3590884158952552830);
void car_H_26(double *state, double *unused, double *out_2399368549525484032);
void car_h_27(double *state, double *unused, double *out_5937191991694674237);
void car_H_27(double *state, double *unused, double *out_961967489595092789);
void car_h_29(double *state, double *unused, double *out_5780005323343545092);
void car_H_29(double *state, double *unused, double *out_1723027166519724306);
void car_h_28(double *state, double *unused, double *out_974811994013381005);
void car_H_28(double *state, double *unused, double *out_3686657438085050557);
void car_h_31(double *state, double *unused, double *out_2926164752394673060);
void car_H_31(double *state, double *unused, double *out_1372780731225532620);
void car_predict(double *in_x, double *in_P, double *in_Q, double dt);
void car_set_mass(double x);
void car_set_rotational_inertia(double x);
void car_set_center_to_front(double x);
void car_set_center_to_rear(double x);
void car_set_stiffness_front(double x);
void car_set_stiffness_rear(double x);
}