
#include "MotorController.h"

MotorController::MotorController() : 
    encoder_pos(0), pwmValue(0), Kp(1.0f), Ki(0.1f), Kd(0.05f),
    integral(0.0f), prev_error(0.0f), prev_time_pid(0), target_flow(0.0f),
    sine_amplitude(0.0f), sine_frequency(0.0f), start_time_mode1(0),
    ultimo_scatto_irq(0), flag_inverti_marcia(false), dir_swing(true), pwm_swing(0.0f) {}

void MotorController::begin() {
    pinMode(PWM_OUT, OUTPUT);
    pinMode(GPIO_OUT_1, OUTPUT); 
    pinMode(GPIO_OUT_2, OUTPUT); 
    pinMode(ENC_A, INPUT); 
    pinMode(ENC_B, INPUT);
    pinMode(ENC_Z, INPUT_PULLDOWN);

    volatile Modalita dummyStato = MODE_IDLE;
    setMotor(0, false, false, dummyStato);
    prev_time_pid = millis();
}

void IRAM_ATTR MotorController::encoderTick() {
    static int8_t lookup_table[] = {0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0};
    static uint8_t enc_val = 0;
    enc_val = enc_val << 2;
    enc_val = enc_val | ((digitalRead(ENC_A) << 1) | digitalRead(ENC_B));
    encoder_pos += lookup_table[enc_val & 0b1111];
}

void IRAM_ATTR MotorController::handleEmergencyStop(volatile Modalita& stato) {
    unsigned long tempo_attuale = millis();
    if (tempo_attuale - ultimo_scatto_irq > 200) { // Debounce 200ms
        if (stato == MODE_DEBUG_SWING) {
            flag_inverti_marcia = true;
        } else {
            stato = MODE_IDLE;
            digitalWrite(GPIO_OUT_1, LOW);
            analogWrite(PWM_OUT, 0);
        }
        ultimo_scatto_irq = tempo_attuale;
    }
}

void MotorController::controllaInversioneSwing(volatile Modalita& stato) {
    if (stato == MODE_DEBUG_SWING && flag_inverti_marcia) {
        flag_inverti_marcia = false;
        dir_swing = !dir_swing;
        setMotor(pwm_swing, dir_swing, true, stato);
    }
}

void MotorController::setMotor(float speed, bool dir, bool enable, volatile Modalita& stato) {
    if (stato == MODE_IDLE) {
        enable = false;
        speed = 0.0f;
    }
    digitalWrite(GPIO_OUT_1, enable ? HIGH : LOW);
    digitalWrite(GPIO_OUT_2, dir ? HIGH : LOW);

    if (!enable) {
        analogWrite(PWM_OUT, 0);
        return;
    }

    float normalized_speed = (speed <= 1.0f && speed >= 0.0f) ? speed : (speed / 255.0f);
    if (normalized_speed > 1.0f) normalized_speed = 1.0f;
    if (normalized_speed < 0.0f) normalized_speed = 0.0f;

    int minPWM = 26;  
    int maxPWM = 230; 
    pwmValue = minPWM + (int)(normalized_speed * (maxPWM - minPWM));
    analogWrite(PWM_OUT, pwmValue);
}

void MotorController::updatePID(float current_flow, volatile Modalita& stato) {
    if (stato != MODE_LINEAR && stato != MODE_SINUSOIDAL) return;

    unsigned long current_time = millis();
    float dt = (current_time - prev_time_pid) / 1000.0f;
    if (dt <= 0.0f) dt = 0.005f; 
    prev_time_pid = current_time;

    float setpoint = 0.0f;
    if (stato == MODE_LINEAR) {
        setpoint = target_flow;
    } else if (stato == MODE_SINUSOIDAL) {
        float t = (current_time - start_time_mode1) / 1000.0f;
        setpoint = sine_amplitude * sin(2.0 * M_PI * sine_frequency * t);
    }

    float error = setpoint - current_flow;
    integral += error * dt;
    if (integral > 200.0f) integral = 200.0f;
    if (integral < -200.0f) integral = -200.0f;

    float derivative = (error - prev_error) / dt;
    float output = (Kp * error) + (Ki * integral) + (Kd * derivative);
    prev_error = error;

    bool forward = (output >= 0);
    float motor_speed = fabs(output); 
    if (motor_speed > 255.0f) motor_speed = 255.0f;

    setMotor(motor_speed, forward, true, stato);
}

void MotorController::resetPID() {
    integral = 0.0f;
    prev_error = 0.0f;
    prev_time_pid = millis();
}