#include <Arduino.h>
#include <EEPROM.h>

const uint8_t PIN_JOY_X = A0;
const uint8_t PIN_JOY_Y = A1;
const uint8_t BUTTON_PINS[4] = {2, 3, 4, 5};

const uint8_t DEFAULT_BASE_NOTE = 60;
const int DEFAULT_DEADZONE = 40;
const uint16_t DEFAULT_SWEEP_RATE = 150;

uint8_t BASE_NOTE = DEFAULT_BASE_NOTE;
int DEADZONE = DEFAULT_DEADZONE; // radial deadzone radius, raw ADC units, around center
const int CENTER = 512;

const uint8_t MIDI_CHANNEL = 0;   // normal button notes live here
const uint8_t SWEEP_CHANNEL = 1;  // sweep lives on its own channel, no note collisions

const int8_t NEIGHBOR_OFFSETS[4] = {0, 1, 2, 3};

const int JOY_MIN = 0;
const int JOY_MAX = 1023;
const uint8_t OCTAVE_SEMITONES = 12;
const int VELOCITY_MIN = 0;
const int VELOCITY_MAX = 127;
const unsigned long DEBOUNCE_MS = 15;
const unsigned long TELEMETRY_MS = 40;

const uint8_t MIDI_NOTE_ON = 0x90;
const uint8_t MIDI_NOTE_OFF = 0x80;
const uint8_t MIDI_CC = 0xB0;
const uint8_t CC_VOLUME = 7;

// ---------- EEPROM layout ----------
const int EEPROM_MAGIC_ADDR = 0;      // 1 byte
const uint8_t EEPROM_MAGIC_VAL = 0xA6;
const int EEPROM_BASE_ADDR = 1;       // 1 byte
const int EEPROM_DEADZONE_ADDR = 2;   // 2 bytes (int)
const int EEPROM_SWEEP_ON_ADDR = 4;   // 1 byte (0/1)
const int EEPROM_SWEEP_RATE_ADDR = 5; // 2 bytes (uint16_t)

enum Mode { MODE_DEBUG, MODE_MIDI };
Mode currentMode = MODE_MIDI; // boots into MIDI mode; not saved/reset by "X"

bool buttonState[4] = {false, false, false, false};
bool buttonLastReading[4] = {false, false, false, false};
unsigned long buttonLastChange[4] = {0, 0, 0, 0};
uint8_t buttonNoteSounding[4] = {0, 0, 0, 0};

int8_t joyZone = 0;
uint8_t joyVelocity = 0;
uint8_t joyLastSentVelocityButtons = 255;
uint8_t joyLastSentVelocitySweep = 255;
int zoneWidth;
unsigned long lastTelemetry = 0;

// ---------- drone sweep (armed via S:1/S:0, only sounds while a button is held) ----------
bool sweepEnabled = false;    // "armed" flag, toggled from the GUI
bool sweepPrevActive = false; // was it actually sounding last loop (armed AND button held)
uint16_t sweepIntervalMs = DEFAULT_SWEEP_RATE;
int8_t sweepStep = 0;
int8_t sweepDir = 1;
unsigned long lastSweepStep = 0;
uint8_t sweepNoteSounding = 255; // 255 = none currently sounding

String serialLine = "";

void loadSettings() {
  if (EEPROM.read(EEPROM_MAGIC_ADDR) == EEPROM_MAGIC_VAL) {
    EEPROM.get(EEPROM_BASE_ADDR, BASE_NOTE);
    EEPROM.get(EEPROM_DEADZONE_ADDR, DEADZONE);
    uint8_t sweepFlag;
    EEPROM.get(EEPROM_SWEEP_ON_ADDR, sweepFlag);
    sweepEnabled = (sweepFlag == 1);
    EEPROM.get(EEPROM_SWEEP_RATE_ADDR, sweepIntervalMs);
  } else {
    saveSettings();
  }
}

void saveSettings() {
  EEPROM.update(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_VAL);
  EEPROM.put(EEPROM_BASE_ADDR, BASE_NOTE);
  EEPROM.put(EEPROM_DEADZONE_ADDR, DEADZONE);
  EEPROM.put(EEPROM_SWEEP_ON_ADDR, (uint8_t)(sweepEnabled ? 1 : 0));
  EEPROM.put(EEPROM_SWEEP_RATE_ADDR, sweepIntervalMs);
}

void allNotesOff() {
  for (uint8_t i = 0; i < 4; i++) {
    if (buttonState[i]) {
      sendNoteOff(buttonNoteSounding[i], MIDI_CHANNEL);
      buttonState[i] = false;
    }
  }
  if (sweepNoteSounding != 255) {
    sendNoteOff(sweepNoteSounding, SWEEP_CHANNEL);
    sweepNoteSounding = 255;
  }
  sweepPrevActive = false;
}

void resetToDefaults() {
  allNotesOff();
  sweepEnabled = false;
  BASE_NOTE = DEFAULT_BASE_NOTE;
  DEADZONE = DEFAULT_DEADZONE;
  sweepIntervalMs = DEFAULT_SWEEP_RATE;
  saveSettings();

  Serial.print("RESET:"); Serial.print(BASE_NOTE); Serial.print(":");
  Serial.print(DEADZONE); Serial.print(":0:"); Serial.println(sweepIntervalMs);
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < 4; i++) pinMode(BUTTON_PINS[i], INPUT_PULLUP);
  zoneWidth = (JOY_MAX - JOY_MIN + 1) / OCTAVE_SEMITONES;
  loadSettings();
}

void loop() {
  handleSerial();
  handleJoystick();
  handleButtons();
  handleSweep();
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

// Commands: M | D | B:<baseNote> | Z:<deadzoneRadius> | S:1 | S:0 | R:<sweepMs> | X (reset)
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
    saveSettings();
    Serial.print("BASE:"); Serial.println(BASE_NOTE);
  } else if (line.startsWith("Z:")) {
    DEADZONE = line.substring(2).toInt();
    saveSettings();
    Serial.print("DEADZONE:"); Serial.println(DEADZONE);
  } else if (line == "S:1") {
    sweepEnabled = true; // armed -- still silent until a button is held
    saveSettings();
    Serial.println("SWEEP:1");
  } else if (line == "S:0") {
    sweepEnabled = false;
    if (sweepNoteSounding != 255) {
      sendNoteOff(sweepNoteSounding, SWEEP_CHANNEL);
      sweepNoteSounding = 255;
    }
    sweepPrevActive = false;
    saveSettings();
    Serial.println("SWEEP:0");
  } else if (line.startsWith("R:")) {
    sweepIntervalMs = line.substring(2).toInt();
    saveSettings();
    Serial.print("SWEEPRATE:"); Serial.println(sweepIntervalMs);
  } else if (line == "X") {
    resetToDefaults();
  }
}

void handleButtons() {
  for (uint8_t i = 0; i < 4; i++) {
    bool reading = (digitalRead(BUTTON_PINS[i]) == LOW);
    if (reading != buttonLastReading[i]) buttonLastChange[i] = millis();

    if ((millis() - buttonLastChange[i]) > DEBOUNCE_MS && reading != buttonState[i]) {
      buttonState[i] = reading;

      int8_t off = (joyZone + NEIGHBOR_OFFSETS[i]) % OCTAVE_SEMITONES;
      if (off < 0) off += OCTAVE_SEMITONES;
      uint8_t note = BASE_NOTE + off;

      if (buttonState[i]) {
        buttonNoteSounding[i] = note;
        sendNoteOn(note, 100, MIDI_CHANNEL);
        joyLastSentVelocityButtons = 255;
      } else {
        sendNoteOff(buttonNoteSounding[i], MIDI_CHANNEL);
      }
    }
    buttonLastReading[i] = reading;
  }
}

bool anyButtonHeld() {
  for (uint8_t i = 0; i < 4; i++) if (buttonState[i]) return true;
  return false;
}

void handleJoystick() {
  int xRaw = analogRead(PIN_JOY_X);
  int yRaw = analogRead(PIN_JOY_Y);

  if (currentMode == MODE_DEBUG && millis() - lastTelemetry >= TELEMETRY_MS) {
    lastTelemetry = millis();
    Serial.print("POS:"); Serial.print(xRaw); Serial.print(":");
    Serial.print(yRaw); Serial.print(":"); Serial.print(joyZone);
    Serial.print(":"); Serial.println(DEADZONE);
  }

  long dx = xRaw - CENTER;
  long dy = yRaw - CENTER;
  bool inDeadzone = (dx * dx + dy * dy) < ((long)DEADZONE * DEADZONE);

  int effX = inDeadzone ? CENTER : xRaw;
  int effY = inDeadzone ? CENTER : yRaw;

  joyVelocity = constrain(map(effY, JOY_MIN, JOY_MAX, VELOCITY_MIN, VELOCITY_MAX), VELOCITY_MIN, VELOCITY_MAX);
  joyZone = constrain((effX - JOY_MIN) / zoneWidth, 0, OCTAVE_SEMITONES - 1);

  bool held = anyButtonHeld();

  if (held && abs((int)joyVelocity - (int)joyLastSentVelocityButtons) >= 2) {
    sendVolumeCC(joyVelocity, MIDI_CHANNEL);
    joyLastSentVelocityButtons = joyVelocity;
  }
  if (sweepEnabled && held && abs((int)joyVelocity - (int)joyLastSentVelocitySweep) >= 2) {
    sendVolumeCC(joyVelocity, SWEEP_CHANNEL);
    joyLastSentVelocitySweep = joyVelocity;
  }
}

void handleSweep() {
  bool active = sweepEnabled && anyButtonHeld();

  if (active && !sweepPrevActive) {
    // a button was just pressed while sweep is armed -- start a fresh run
    sweepStep = 0;
    sweepDir = 1;
    lastSweepStep = 0;
    joyLastSentVelocitySweep = 255;
  } else if (!active && sweepPrevActive) {
    // last button was just released -- stop immediately
    if (sweepNoteSounding != 255) {
      sendNoteOff(sweepNoteSounding, SWEEP_CHANNEL);
      sweepNoteSounding = 255;
    }
  }
  sweepPrevActive = active;

  if (!active) return;
  if (millis() - lastSweepStep < sweepIntervalMs) return;
  lastSweepStep = millis();

  if (sweepNoteSounding != 255) sendNoteOff(sweepNoteSounding, SWEEP_CHANNEL);

  uint8_t note = BASE_NOTE + sweepStep;
  sendNoteOn(note, 100, SWEEP_CHANNEL);
  sweepNoteSounding = note;

  sweepStep += sweepDir;
  if (sweepStep >= (int8_t)(OCTAVE_SEMITONES - 1)) {
    sweepStep = OCTAVE_SEMITONES - 1;
    sweepDir = -1;
  } else if (sweepStep <= 0) {
    sweepStep = 0;
    sweepDir = 1;
  }
}

void sendNoteOn(uint8_t note, uint8_t velocity, uint8_t channel) {
  if (currentMode == MODE_MIDI) {
    Serial.write(MIDI_NOTE_ON | channel);
    Serial.write(note);
    Serial.write(velocity);
  } else {
    Serial.print("ON:"); Serial.print(note); Serial.print(":");
    Serial.print(velocity); Serial.print(":ch"); Serial.println(channel);
  }
}

void sendNoteOff(uint8_t note, uint8_t channel) {
  if (currentMode == MODE_MIDI) {
    Serial.write(MIDI_NOTE_OFF | channel);
    Serial.write(note);
    Serial.write((uint8_t)0);
  } else {
    Serial.print("OFF:"); Serial.print(note); Serial.print(":ch"); Serial.println(channel);
  }
}

void sendVolumeCC(uint8_t value, uint8_t channel) {
  if (currentMode == MODE_MIDI) {
    Serial.write(MIDI_CC | channel);
    Serial.write(CC_VOLUME);
    Serial.write(value);
  } else {
    Serial.print("CC7:"); Serial.print(value); Serial.print(":ch"); Serial.println(channel);
  }
}