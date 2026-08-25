
#ifndef MOTOR_CONTROLLER_H
#define MOTOR_CONTROLLER_H

#include "Config.h"

class MotorController {
public:
    MotorController();
    void begin();
    void setMotor(float speed, bool dir, bool enable, volatile Modalita& stato);
    void updatePID(float current_flow, volatile Modalita& stato);
    
    // Gestione interna degli Interrupt legati al motore
    void IRAM_ATTR encoderTick();
    void IRAM_ATTR handleEmergencyStop(volatile Modalita& stato);
    void controllaInversioneSwing(volatile Modalita& stato);

    // Getters & Setters
    long getEncoderPos() const { return encoder_pos; }
    void azzeraEncoder() { encoder_pos = 0; }
    int getPwmValue() const { return pwmValue; }
    
    void setTargetFlow(float flow) { target_flow = flow; resetPID(); }
    void setSineParams(float amp, float freq) { sine_amplitude = amp; sine_frequency = freq; start_time_mode1 = millis(); resetPID(); }
    void avviaSwing(float pwm) { pwm_swing = pwm; dir_swing = true; flag_inverti_marcia = false; }

private:
    volatile long encoder_pos;
    int pwmValue;

    // Variabili PID
    float Kp, Ki, Kd;
    float integral, prev_error;
    unsigned long prev_time_pid;

    // Target Traiettorie
    float target_flow;
    float sine_amplitude;
    float sine_frequency;
    unsigned long start_time_mode1;

    // Variabili Modalità 520 Ping-Pong
    volatile unsigned long ultimo_scatto_irq;
    volatile bool flag_inverti_marcia;
    bool dir_swing;
    float pwm_swing;

    void resetPID();
};

#endif