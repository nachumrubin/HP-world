// Engine-agnostic broom flight model.
//
// This file deliberately has no Unreal dependencies so the flight feel can be unit-tested and
// tuned outside the editor (see Tests/FlightModel). UBroomMovementComponent wraps it.
//
// Conventions match Unreal: centimetres, degrees, X forward, Y right, Z up.
// Positive pitch = nose up, positive yaw = turn right, positive roll = bank right.

#pragma once

namespace HPFlight
{
	struct FFlightVec
	{
		double X = 0.0;
		double Y = 0.0;
		double Z = 0.0;

		FFlightVec() = default;
		FFlightVec(double InX, double InY, double InZ) : X(InX), Y(InY), Z(InZ) {}

		FFlightVec operator+(const FFlightVec& O) const { return { X + O.X, Y + O.Y, Z + O.Z }; }
		FFlightVec operator-(const FFlightVec& O) const { return { X - O.X, Y - O.Y, Z - O.Z }; }
		FFlightVec operator*(double S) const { return { X * S, Y * S, Z * S }; }
		FFlightVec& operator+=(const FFlightVec& O) { X += O.X; Y += O.Y; Z += O.Z; return *this; }

		double Dot(const FFlightVec& O) const { return X * O.X + Y * O.Y + Z * O.Z; }
		double Length() const;
	};

	// Designer-facing tuning. Speeds in cm/s, angles in degrees, rates in deg/s, responses in 1/s.
	struct FBroomTuning
	{
		double CruiseSpeed = 2500.0;        // ~90 km/h, where the broom settles with no throttle
		double MaxSpeed = 3500.0;           // top speed under normal throttle
		double BoostSpeed = 5500.0;         // "Firebolt" boost top speed
		double TerminalSpeed = 7500.0;      // absolute cap, reachable only in a boosted dive
		double Acceleration = 1400.0;
		double BoostAcceleration = 2600.0;
		double BrakeDeceleration = 2200.0;
		double CoastResponse = 0.6;         // how quickly speed returns to cruise (or to hover) when coasting
		double OverspeedDrag = 0.8;         // how quickly excess dive speed bleeds off
		double Gravity = 980.0;
		double DiveGravityScale = 0.55;     // fraction of gravity traded along the flight path (dive = faster)

		double HoverSpeedThreshold = 450.0; // below this the broom behaves like a hovering broom
		double HoverVerticalSpeed = 700.0;
		double HoverYawRate = 90.0;

		double MaxPitchRate = 75.0;
		double MaxPitchAngle = 80.0;
		double PitchAutoLevel = 0.5;        // gentle return to level flight when the stick is released
		double MaxBankAngle = 55.0;
		double BankResponse = 4.0;
		double MaxTurnRate = 65.0;          // yaw rate at full bank
		double VelocityGrip = 3.5;          // how fast velocity follows the nose (lower = more drift/momentum)

		double MinClearance = 120.0;        // never fly closer than this to ground or water
		double ClearanceStiffness = 4.0;    // softness of the ground/water floor (also the dive pull-up)
		double SkimHeight = 400.0;          // below this we count as skimming (water wake, grass FX)
		double PullUpLeadTime = 2.0;        // seconds before impact that the automatic dive pull-up begins

		double SoftBoundaryRadius = 300000.0; // 3 km from world origin: mist + wind turns you back
		double BoundaryFadeWidth = 30000.0;
		double BoundaryTurnRate = 60.0;
		double SoftCeiling = 70000.0;       // 700 m
		double CeilingFadeHeight = 10000.0;

		double MaxSubstep = 1.0 / 60.0;
	};

	struct FBroomInput
	{
		double Pitch = 0.0;    // -1..1, + = nose up
		double Turn = 0.0;     // -1..1, + = right
		double Throttle = 0.0; // -1..1, + = accelerate, - = brake
		double Vertical = 0.0; // -1..1, hover ascend/descend
		bool bBoost = false;
	};

	// What the world around the broom looks like this frame (filled in by the engine layer).
	struct FBroomEnvironment
	{
		double HeightAboveSurface = 1.0e9;
		bool bSurfaceIsWater = false;
	};

	struct FBroomState
	{
		FFlightVec Position;
		FFlightVec Velocity;
		double Speed = 0.0; // commanded airspeed along the nose
		double Pitch = 0.0;
		double Yaw = 0.0;
		double Roll = 0.0;
	};

	// Outputs used to drive camera, audio and VFX.
	struct FBroomTelemetry
	{
		double SpeedAlpha = 0.0; // 0 = still, 1 = boost speed
		double GForce = 1.0;
		bool bHovering = true;
		bool bBoosting = false;
		bool bDiving = false;
		bool bSkimming = false;
		bool bSkimmingWater = false;
		bool bOutsideBoundary = false;
	};

	class FBroomFlightModel
	{
	public:
		FBroomTuning Tuning;
		FBroomState State;
		FBroomTelemetry Telemetry;

		void Reset(const FFlightVec& Position, double Yaw);
		void Step(const FBroomInput& Input, const FBroomEnvironment& Environment, double DeltaSeconds);

		// Call after the engine's sweep hit something. Removes velocity into the surface, scrubs speed
		// and returns impact severity in 0..1 (useful for camera shake / audio).
		double ApplyImpact(const FFlightVec& SurfaceNormal);

		FFlightVec GetForward() const;

	private:
		void Substep(const FBroomInput& Input, const FBroomEnvironment& Environment, double Dt);
		void UpdateSpeed(const FBroomInput& Input, double HoverBlend, double Dt);
		void UpdateAttitude(const FBroomInput& Input, double HoverBlend, double Dt);
		void ApplyWorldLimits(double Dt);
	};
}
