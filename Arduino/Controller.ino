#include <Arduino.h>

const uint8_t PIN_JOY_X = A0;
const uint8_t PIN_JOY_Y = A1;
const uint8_t BUTTON_PINS[4] = {2, 3, 4, 5};

uint8_t BASE_NOTE = 60;
int DEADZONE = 15;
const uint8_t MIDI_CHANNEL = 0;
const int8_t NEIGHBOR_OFFSETS[4] = {0, 1, 2, 3};

const int JOY_MIN = 0;
const int JOY_MAX = 1023;
const uint8_t OCTAVE_SEMITONES = 12;
const int VELOCITY_MIN = 0;
const int VELOCITY_MAX = 127;
const unsigned long DEBOUNCE_MS = 15;

const uint8_t MIDI_NOTE_ON = 0x90;
const uint8_t MIDI_NOTE_OFF = 0x80;
const uint8_t MIDI_CC = 0xB0;
const uint8_t CC_VOLUME = 7;

enum Mode { MODE_DEBUG, MODE_MIDI };
Mode currentMode = MODE_DEBUG;

bool buttonState[4] = {false, false, false, false};
bool buttonLastReading[4] = {false, false, false, false};
unsigned long buttonLastChange[4] = {0, 0, 0, 0};
uint8_t buttonNoteSounding[4] = {0, 0, 0, 0};

int8_t joyZone = -1;
int zoneWidth;
uint8_t joyVelocity = 0;
uint8_t joyLastSentVelocity = 255;

String serialLine = "";

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < 4; i++) pinMode(BUTTON_PINS[i], INPUT_PULLUP);
  zoneWidth = (JOY_MAX - JOY_MIN + 1) / OCTAVE_SEMITONES;
}

void loop() {
  handleSerial();
  handleJoystick();
  handleButtons();
}

void handleSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      processCommand(serialLine);
      serialLine = "";
    } else if (c != '\r') {
      serialLine += c;
    }
  }
}

// Commands: M | D | B:<baseNote> | Z:<deadzone>
void processCommand(String line) {
  line.trim();
  if (line.length() == 0) return;

  if (line == "M") {
    currentMode = MODE_MIDI;
  } else if (line == "D") {
    currentMode = MODE_DEBUG;
    Serial.println("DEBUG_MODE");
  } else if (line.startsWith("B:")) {
    BASE_NOTE = line.substring(2).toInt();
    Serial.print("BASE:"); Serial.println(BASE_NOTE);
  } else if (line.startsWith("Z:")) {
    DEADZONE = line.substring(2).toInt();
    Serial.print("DEADZONE:"); Serial.println(DEADZONE);
  }
}

void handleButtons() {
  for (uint8_t i = 0; i < 4; i++) {
    bool reading = (digitalRead(BUTTON_PINS[i]) == LOW);
    if (reading != buttonLastReading[i]) buttonLastChange[i] = millis();

    if ((millis() - buttonLastChange[i]) > DEBOUNCE_MS && reading != buttonState[i]) {
      buttonState[i] = reading;
      int8_t zone = (joyZone < 0) ? 0 : joyZone;
      uint8_t note = BASE_NOTE + zone + NEIGHBOR_OFFSETS[i];

      if (buttonState[i]) {
        buttonNoteSounding[i] = note;
        sendNoteOn(note, 100);
      } else {
        sendNoteOff(buttonNoteSounding[i]);
      }
    }
    buttonLastReading[i] = reading;
  }
}

void handleJoystick() {
  int xRaw = analogRead(PIN_JOY_X);
  int yRaw = analogRead(PIN_JOY_Y);

  uint8_t velocity = constrain(map(yRaw, JOY_MIN, JOY_MAX, VELOCITY_MIN, VELOCITY_MAX), VELOCITY_MIN, VELOCITY_MAX);
  joyVelocity = velocity;

  int8_t rawZone = constrain((xRaw - JOY_MIN) / zoneWidth, 0, OCTAVE_SEMITONES - 1);

  if (joyZone == -1) {
    joyZone = rawZone;
    sendNoteOn(BASE_NOTE + joyZone, joyVelocity);
    joyLastSentVelocity = joyVelocity;
    return;
  }

  int lowerBound = joyZone * zoneWidth;
  int upperBound = lowerBound + zoneWidth - 1;

  if (xRaw < lowerBound - DEADZONE || xRaw > upperBound + DEADZONE) {
    if (rawZone != joyZone) {
      sendNoteOff(BASE_NOTE + joyZone);
      joyZone = rawZone;
      sendNoteOn(BASE_NOTE + joyZone, joyVelocity);
      joyLastSentVelocity = joyVelocity;
    }
  } else if (abs((int)joyVelocity - (int)joyLastSentVelocity) >= 2) {
    sendVolumeCC(joyVelocity);
    joyLastSentVelocity = joyVelocity;
  }
}

void sendNoteOn(uint8_t note, uint8_t velocity) {
  if (currentMode == MODE_MIDI) {
    Serial.write(MIDI_NOTE_ON | MIDI_CHANNEL);
    Serial.write(note);
    Serial.write(velocity);
  } else {
    Serial.print("ON:"); Serial.print(note); Serial.print(":"); Serial.println(velocity);
  }
}

void sendNoteOff(uint8_t note) {
  if (currentMode == MODE_MIDI) {
    Serial.write(MIDI_NOTE_OFF | MIDI_CHANNEL);
    Serial.write(note);
    Serial.write((uint8_t)0);
  } else {
    Serial.print("OFF:"); Serial.println(note);
  }
}

void sendVolumeCC(uint8_t value) {
  if (currentMode == MODE_MIDI) {
    Serial.write(MIDI_CC | MIDI_CHANNEL);
    Serial.write(CC_VOLUME);
    Serial.write(value);
  } else {
    Serial.print("CC7:"); Serial.println(value);
  }
}