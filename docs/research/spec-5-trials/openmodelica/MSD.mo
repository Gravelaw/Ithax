// Spec 5 trial: the mass-spring-damper benchmark in the Modelica Standard Library 4.1.0.
// m x'' + d x' + c x = 0, m = 1 kg, c = 4 N/m, d = 0.4 N.s/m, x(0) = 1 m, x'(0) = 0.
// Built into an FMI 2.0 Co-Simulation FMU by build.mos (CI workflow spec5-trials.yml).
model MSD
  Modelica.Mechanics.Translational.Components.Fixed fixed;
  Modelica.Mechanics.Translational.Components.Spring spring(c = 4, s_rel0 = 0);
  Modelica.Mechanics.Translational.Components.Damper damper(d = 0.4);
  Modelica.Mechanics.Translational.Components.Mass mass(m = 1, L = 0,
    s(start = 1, fixed = true), v(start = 0, fixed = true));
  Modelica.Blocks.Interfaces.RealOutput x(unit = "m") "Position of the mass";
  Modelica.Blocks.Interfaces.RealOutput v(unit = "m/s") "Velocity of the mass";
equation
  connect(fixed.flange, spring.flange_a);
  connect(fixed.flange, damper.flange_a);
  connect(spring.flange_b, mass.flange_a);
  connect(damper.flange_b, mass.flange_a);
  x = mass.s;
  v = mass.v;
end MSD;
