/* A hand-written FMI 2.0 Model Exchange FMU: a mass, spring and damper.
   It only states the equations, m x'' + c x' + k x = 0, as derivatives;
   FMPy's integrator (CVODE) solves them. Research trial, not product code. */
#include <stdlib.h>
#include <string.h>
#include "fmi2Functions.h"

/* value references: 0 x, 1 v, 2 der(x), 3 der(v), 4 m, 5 c, 6 k, 7 x0, 8 v0 */
typedef struct { double r[9]; double time; } Model;

static void deriv(Model *M) { M->r[2] = M->r[1]; M->r[3] = -(M->r[5]*M->r[1] + M->r[6]*M->r[0]) / M->r[4]; }

const char* fmi2GetTypesPlatform(void) { return fmi2TypesPlatform; }
const char* fmi2GetVersion(void) { return fmi2Version; }
fmi2Status fmi2SetDebugLogging(fmi2Component c, fmi2Boolean l, size_t n, const fmi2String cat[]) { return fmi2OK; }
fmi2Component fmi2Instantiate(fmi2String n, fmi2Type t, fmi2String g, fmi2String r, const fmi2CallbackFunctions* f, fmi2Boolean v, fmi2Boolean l) {
  Model *M = calloc(1, sizeof(Model));
  M->r[4] = 1.0; M->r[5] = 0.4; M->r[6] = 4.0; M->r[7] = 1.0; M->r[8] = 0.0;
  return M;
}
void fmi2FreeInstance(fmi2Component c) { free(c); }
fmi2Status fmi2SetupExperiment(fmi2Component c, fmi2Boolean a, fmi2Real tol, fmi2Real t0, fmi2Boolean b, fmi2Real t1) { ((Model*)c)->time = t0; return fmi2OK; }
fmi2Status fmi2EnterInitializationMode(fmi2Component c) { return fmi2OK; }
fmi2Status fmi2ExitInitializationMode(fmi2Component c) { Model *M = c; M->r[0] = M->r[7]; M->r[1] = M->r[8]; deriv(M); return fmi2OK; }
fmi2Status fmi2Terminate(fmi2Component c) { return fmi2OK; }
fmi2Status fmi2Reset(fmi2Component c) { return fmi2OK; }
fmi2Status fmi2GetReal(fmi2Component c, const fmi2ValueReference vr[], size_t n, fmi2Real v[]) { Model *M = c; deriv(M); for (size_t i = 0; i < n; i++) v[i] = M->r[vr[i]]; return fmi2OK; }
fmi2Status fmi2SetReal(fmi2Component c, const fmi2ValueReference vr[], size_t n, const fmi2Real v[]) { Model *M = c; for (size_t i = 0; i < n; i++) M->r[vr[i]] = v[i]; return fmi2OK; }
fmi2Status fmi2GetInteger(fmi2Component c, const fmi2ValueReference vr[], size_t n, fmi2Integer v[]) { return n ? fmi2Error : fmi2OK; }
fmi2Status fmi2GetBoolean(fmi2Component c, const fmi2ValueReference vr[], size_t n, fmi2Boolean v[]) { return n ? fmi2Error : fmi2OK; }
fmi2Status fmi2GetString(fmi2Component c, const fmi2ValueReference vr[], size_t n, fmi2String v[]) { return n ? fmi2Error : fmi2OK; }
fmi2Status fmi2SetInteger(fmi2Component c, const fmi2ValueReference vr[], size_t n, const fmi2Integer v[]) { return n ? fmi2Error : fmi2OK; }
fmi2Status fmi2SetBoolean(fmi2Component c, const fmi2ValueReference vr[], size_t n, const fmi2Boolean v[]) { return n ? fmi2Error : fmi2OK; }
fmi2Status fmi2SetString(fmi2Component c, const fmi2ValueReference vr[], size_t n, const fmi2String v[]) { return n ? fmi2Error : fmi2OK; }
fmi2Status fmi2GetFMUstate(fmi2Component c, fmi2FMUstate* s) { return fmi2Error; }
fmi2Status fmi2SetFMUstate(fmi2Component c, fmi2FMUstate s) { return fmi2Error; }
fmi2Status fmi2FreeFMUstate(fmi2Component c, fmi2FMUstate* s) { return fmi2Error; }
fmi2Status fmi2SerializedFMUstateSize(fmi2Component c, fmi2FMUstate s, size_t* n) { return fmi2Error; }
fmi2Status fmi2SerializeFMUstate(fmi2Component c, fmi2FMUstate s, fmi2Byte b[], size_t n) { return fmi2Error; }
fmi2Status fmi2DeSerializeFMUstate(fmi2Component c, const fmi2Byte b[], size_t n, fmi2FMUstate* s) { return fmi2Error; }
fmi2Status fmi2GetDirectionalDerivative(fmi2Component c, const fmi2ValueReference u[], size_t nu, const fmi2ValueReference z[], size_t nz, const fmi2Real dv[], fmi2Real dz[]) { return fmi2Error; }
fmi2Status fmi2EnterEventMode(fmi2Component c) { return fmi2OK; }
fmi2Status fmi2NewDiscreteStates(fmi2Component c, fmi2EventInfo* e) { memset(e, 0, sizeof *e); return fmi2OK; }
fmi2Status fmi2EnterContinuousTimeMode(fmi2Component c) { return fmi2OK; }
fmi2Status fmi2CompletedIntegratorStep(fmi2Component c, fmi2Boolean nse, fmi2Boolean* e, fmi2Boolean* t) { *e = fmi2False; *t = fmi2False; return fmi2OK; }
fmi2Status fmi2SetTime(fmi2Component c, fmi2Real t) { ((Model*)c)->time = t; return fmi2OK; }
fmi2Status fmi2SetContinuousStates(fmi2Component c, const fmi2Real x[], size_t n) { Model *M = c; M->r[0] = x[0]; M->r[1] = x[1]; return fmi2OK; }
fmi2Status fmi2GetDerivatives(fmi2Component c, fmi2Real d[], size_t n) { Model *M = c; deriv(M); d[0] = M->r[2]; d[1] = M->r[3]; return fmi2OK; }
fmi2Status fmi2GetEventIndicators(fmi2Component c, fmi2Real e[], size_t n) { return fmi2OK; }
fmi2Status fmi2GetContinuousStates(fmi2Component c, fmi2Real x[], size_t n) { Model *M = c; x[0] = M->r[0]; x[1] = M->r[1]; return fmi2OK; }
fmi2Status fmi2GetNominalsOfContinuousStates(fmi2Component c, fmi2Real x[], size_t n) { x[0] = 1; x[1] = 1; return fmi2OK; }
fmi2Status fmi2SetRealInputDerivatives(fmi2Component c, const fmi2ValueReference vr[], size_t n, const fmi2Integer o[], const fmi2Real v[]) { return fmi2Error; }
fmi2Status fmi2GetRealOutputDerivatives(fmi2Component c, const fmi2ValueReference vr[], size_t n, const fmi2Integer o[], fmi2Real v[]) { return fmi2Error; }
fmi2Status fmi2DoStep(fmi2Component c, fmi2Real t, fmi2Real h, fmi2Boolean b) { return fmi2Error; }
fmi2Status fmi2CancelStep(fmi2Component c) { return fmi2Error; }
fmi2Status fmi2GetStatus(fmi2Component c, const fmi2StatusKind s, fmi2Status* v) { return fmi2Error; }
fmi2Status fmi2GetRealStatus(fmi2Component c, const fmi2StatusKind s, fmi2Real* v) { return fmi2Error; }
fmi2Status fmi2GetIntegerStatus(fmi2Component c, const fmi2StatusKind s, fmi2Integer* v) { return fmi2Error; }
fmi2Status fmi2GetBooleanStatus(fmi2Component c, const fmi2StatusKind s, fmi2Boolean* v) { return fmi2Error; }
fmi2Status fmi2GetStringStatus(fmi2Component c, const fmi2StatusKind s, fmi2String* v) { return fmi2Error; }
