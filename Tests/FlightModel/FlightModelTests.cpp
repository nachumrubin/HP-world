// Unit tests for the engine-agnostic broom flight model.
// Build & run:  cmake -S Tests/FlightModel -B Tests/FlightModel/build && cmake --build Tests/FlightModel/build && ./Tests/FlightModel/build/FlightModelTests

#include "BroomFlightModel.h"

#include <cmath>
#include <cstdio>
#include <functional>
#include <string>
#include <vector>

using namespace HPFlight;

namespace
{
	int GFailures = 0;

	void Expect(bool bCondition, const std::string& Message)
	{
		if (!bCondition)
		{
			++GFailures;
			std::printf("    FAIL: %s\n", Message.c_str());
		}
	}

	std::string Num(double V)
	{
		char Buffer[64];
		std::snprintf(Buffer, sizeof(Buffer), "%.1f", V);
		return Buffer;
	}

	// Flat ground at Z = 0 (optionally water) under the broom.
	FBroomEnvironment Ground(const FBroomFlightModel& Model, bool bWater = false)
	{
		FBroomEnvironment Env;
		Env.HeightAboveSurface = Model.State.Position.Z;
		Env.bSurfaceIsWater = bWater;
		return Env;
	}

	void Run(FBroomFlightModel& Model, const FBroomInput& Input, double Seconds, double Fps = 60.0, bool bGround = false)
	{
		const double Dt = 1.0 / Fps;
		for (double T = 0.0; T < Seconds; T += Dt)
		{
			Model.Step(Input, bGround ? Ground(Model) : FBroomEnvironment(), Dt);
		}
	}

	FBroomFlightModel MakeCruising(double Altitude = 10000.0)
	{
		FBroomFlightModel Model;
		Model.Reset({ 0.0, 0.0, Altitude }, 0.0);
		Model.State.Speed = Model.Tuning.CruiseSpeed;
		Model.State.Velocity = { Model.Tuning.CruiseSpeed, 0.0, 0.0 };
		return Model;
	}

	bool Finite(const FBroomFlightModel& Model)
	{
		const FBroomState& S = Model.State;
		return std::isfinite(S.Position.X) && std::isfinite(S.Position.Y) && std::isfinite(S.Position.Z)
			&& std::isfinite(S.Velocity.Length()) && std::isfinite(S.Pitch) && std::isfinite(S.Yaw) && std::isfinite(S.Roll);
	}

	void TestStartsHovering()
	{
		FBroomFlightModel Model;
		Model.Reset({ 0.0, 0.0, 500.0 }, 0.0);
		Run(Model, {}, 3.0);
		Expect(Model.Telemetry.bHovering, "idle broom should hover");
		Expect(Model.State.Velocity.Length() < 1.0, "idle broom should not drift, v=" + Num(Model.State.Velocity.Length()));
	}

	void TestHoverVertical()
	{
		FBroomFlightModel Model;
		Model.Reset({ 0.0, 0.0, 500.0 }, 0.0);
		FBroomInput Up;
		Up.Vertical = 1.0;
		Run(Model, Up, 2.0);
		Expect(Model.State.Position.Z > 1500.0, "hover ascend should climb, z=" + Num(Model.State.Position.Z));
	}

	void TestHoverPitchLifts()
	{
		FBroomFlightModel Model;
		Model.Reset({ 0.0, 0.0, 500.0 }, 0.0);
		FBroomInput NoseUp;
		NoseUp.Pitch = 1.0;
		Run(Model, NoseUp, 2.0);
		Expect(Model.State.Position.Z > 1500.0, "pulling up while hovering should rise, z=" + Num(Model.State.Position.Z));
		Expect(std::abs(Model.State.Pitch) < 5.0, "a hovering broom stays level, pitch=" + Num(Model.State.Pitch));
	}

	void TestHoverPivot()
	{
		FBroomFlightModel Model;
		Model.Reset({ 0.0, 0.0, 500.0 }, 0.0);
		FBroomInput Turn;
		Turn.Turn = 1.0;
		Run(Model, Turn, 1.0);
		Expect(Model.State.Yaw > 60.0, "hovering broom should pivot in place, yaw=" + Num(Model.State.Yaw));
		Expect(Model.State.Velocity.Length() < 50.0, "pivot should not move the broom");
	}

	void TestThrottleReachesMaxSpeed()
	{
		FBroomFlightModel Model;
		Model.Reset({ 0.0, 0.0, 10000.0 }, 0.0);
		FBroomInput Go;
		Go.Throttle = 1.0;
		Run(Model, Go, 6.0);
		Expect(std::abs(Model.State.Speed - Model.Tuning.MaxSpeed) < 50.0, "full throttle should reach MaxSpeed, speed=" + Num(Model.State.Speed));
		Expect(!Model.Telemetry.bHovering, "should be flying");
		Expect(std::abs(Model.State.Position.Z - 10000.0) < 100.0, "level flight should hold altitude, z=" + Num(Model.State.Position.Z));
	}

	void TestCoastSettlesAtCruise()
	{
		FBroomFlightModel Model = MakeCruising();
		Model.State.Speed = Model.Tuning.MaxSpeed;
		Run(Model, {}, 10.0);
		Expect(std::abs(Model.State.Speed - Model.Tuning.CruiseSpeed) < 50.0, "coasting should settle at cruise, speed=" + Num(Model.State.Speed));
	}

	void TestBrakeToHover()
	{
		FBroomFlightModel Model = MakeCruising();
		FBroomInput Brake;
		Brake.Throttle = -1.0;
		Run(Model, Brake, 2.0);
		Run(Model, {}, 4.0);
		Expect(Model.Telemetry.bHovering, "braking hard then releasing should leave the broom hovering, speed=" + Num(Model.State.Speed));
	}

	void TestBoost()
	{
		FBroomFlightModel Model = MakeCruising();
		FBroomInput Boost;
		Boost.bBoost = true;
		Run(Model, Boost, 5.0);
		Expect(Model.State.Speed > Model.Tuning.MaxSpeed + 1000.0, "boost should exceed MaxSpeed, speed=" + Num(Model.State.Speed));
		Expect(Model.Telemetry.bBoosting, "telemetry should report boosting");
	}

	void TestBankedTurnRight()
	{
		FBroomFlightModel Model = MakeCruising();
		FBroomInput Right;
		Right.Turn = 1.0;
		Run(Model, Right, 1.0);
		Expect(Model.State.Roll > 30.0, "turning right should bank right, roll=" + Num(Model.State.Roll));
		Expect(Model.State.Yaw > 20.0, "turning right should increase yaw, yaw=" + Num(Model.State.Yaw));
		Expect(Model.State.Position.Y > 0.0, "turning right should move toward +Y");
		Expect(Model.Telemetry.GForce > 1.5, "a hard turn should pull G, g=" + Num(Model.Telemetry.GForce));
	}

	void TestDiveGainsSpeedClimbLoses()
	{
		FBroomFlightModel Dive = MakeCruising(50000.0);
		Dive.State.Pitch = -60.0;
		FBroomInput Hold;
		Hold.Pitch = -0.3; // keep the nose down against auto-level
		Run(Dive, Hold, 3.0);
		Expect(Dive.State.Speed > Dive.Tuning.CruiseSpeed + 500.0, "dive should gain speed, speed=" + Num(Dive.State.Speed));
		Expect(Dive.Telemetry.bDiving, "telemetry should report diving");

		FBroomFlightModel Climb = MakeCruising();
		Climb.State.Pitch = 45.0;
		FBroomInput Up;
		Up.Pitch = 0.2;
		Run(Climb, Up, 2.0);
		Expect(Climb.State.Speed < Climb.Tuning.CruiseSpeed, "climb should bleed speed, speed=" + Num(Climb.State.Speed));
	}

	void TestAutoLevel()
	{
		FBroomFlightModel Model = MakeCruising();
		Model.State.Pitch = 30.0;
		Run(Model, {}, 6.0);
		Expect(std::abs(Model.State.Pitch) < 3.0, "releasing the stick should level the nose, pitch=" + Num(Model.State.Pitch));
		Expect(std::abs(Model.State.Roll) < 1.0, "releasing turn should level the wings");
	}

	void TestGroundClearanceInDive()
	{
		FBroomFlightModel Model = MakeCruising(6000.0);
		Model.State.Pitch = -70.0;
		Model.State.Speed = 6000.0;
		Model.State.Velocity = Model.GetForward() * Model.State.Speed; // already established in the dive
		FBroomInput Dive;
		Dive.Pitch = -1.0;
		Dive.bBoost = true;
		double Lowest = 1.0e9;
		double PeakG = 0.0;
		const double Dt = 1.0 / 60.0;
		for (int I = 0; I < 600; ++I)
		{
			Model.Step(Dive, Ground(Model), Dt);
			Lowest = std::min(Lowest, Model.State.Position.Z);
			PeakG = std::max(PeakG, Model.Telemetry.GForce);
		}
		Expect(PeakG < 8.0, "pull-up should be a swoop, not a slam, peak g=" + Num(PeakG));
		Expect(Lowest > Model.Tuning.MinClearance * 0.5, "a full-speed dive must pull up before the ground, lowest=" + Num(Lowest));
		Expect(Model.State.Velocity.Length() > 2000.0, "pull-up should convert the dive into fast level flight");
	}

	void TestWaterSkim()
	{
		FBroomFlightModel Model = MakeCruising(250.0);
		const double Dt = 1.0 / 60.0;
		for (int I = 0; I < 60; ++I)
		{
			Model.Step({}, Ground(Model, true), Dt);
		}
		Expect(Model.Telemetry.bSkimmingWater, "flying low over water should report skimming");
		Expect(Model.State.Position.Z >= Model.Tuning.MinClearance - 1.0, "must stay above water");
	}

	void TestHoverCannotSinkIntoGround()
	{
		FBroomFlightModel Model;
		Model.Reset({ 0.0, 0.0, 300.0 }, 0.0);
		FBroomInput Down;
		Down.Vertical = -1.0;
		Run(Model, Down, 3.0, 60.0, true);
		Expect(Model.State.Position.Z > Model.Tuning.MinClearance * 0.9, "hover descent should stop at clearance, z=" + Num(Model.State.Position.Z));
	}

	void TestBoundaryTurnsBack()
	{
		FBroomFlightModel Model = MakeCruising();
		Model.State.Position.X = Model.Tuning.SoftBoundaryRadius - 1000.0;
		FBroomInput Go;
		Go.Throttle = 1.0;
		double Farthest = 0.0;
		const double Dt = 1.0 / 60.0;
		for (int I = 0; I < 60 * 60; ++I)
		{
			Model.Step(Go, {}, Dt);
			const double R = std::sqrt(Model.State.Position.X * Model.State.Position.X + Model.State.Position.Y * Model.State.Position.Y);
			Farthest = std::max(Farthest, R);
		}
		const double Hard = Model.Tuning.SoftBoundaryRadius + Model.Tuning.BoundaryFadeWidth;
		Expect(Farthest <= Hard + 500.0, "should never escape the boundary, farthest=" + Num(Farthest));
		Expect(Model.State.Position.X < Model.Tuning.SoftBoundaryRadius, "wind should have turned the broom back inside");
	}

	void TestCeiling()
	{
		FBroomFlightModel Model = MakeCruising(FBroomTuning().SoftCeiling - 1000.0);
		Model.State.Pitch = 60.0;
		FBroomInput Climb;
		Climb.Pitch = 1.0;
		Climb.bBoost = true;
		Run(Model, Climb, 30.0);
		Expect(Model.State.Position.Z <= Model.Tuning.SoftCeiling + Model.Tuning.CeilingFadeHeight + 1.0,
			"should never climb above the hard ceiling, z=" + Num(Model.State.Position.Z));
	}

	void TestImpact()
	{
		FBroomFlightModel Model = MakeCruising();
		const double Severity = Model.ApplyImpact({ -1.0, 0.0, 0.0 }); // flying straight into a wall
		Expect(Severity > 0.5, "head-on impact should be severe, s=" + Num(Severity));
		Expect(Model.State.Velocity.X <= 1e-6, "velocity into the wall should be removed");
		Expect(Model.State.Speed < Model.Tuning.CruiseSpeed * 0.5, "head-on impact should scrub speed");

		FBroomFlightModel Glance = MakeCruising();
		Glance.State.Velocity = { 2500.0, 0.0, -200.0 };
		const double Small = Glance.ApplyImpact({ 0.0, 0.0, 1.0 }); // brushing the ground
		Expect(Small < 0.1, "glancing contact should be mild, s=" + Num(Small));
		Expect(Glance.ApplyImpact({ 1.0, 0.0, 0.0 }) == 0.0, "moving away from a surface is not an impact");
	}

	void TestFrameRateIndependence()
	{
		FBroomInput Input;
		Input.Throttle = 1.0;
		Input.Turn = 0.6;
		Input.Pitch = 0.3;

		FBroomFlightModel A = MakeCruising();
		FBroomFlightModel B = MakeCruising();
		Run(A, Input, 4.0, 30.0);
		Run(B, Input, 4.0, 144.0);
		const double Drift = (A.State.Position - B.State.Position).Length();
		Expect(Drift < 300.0, "30 fps and 144 fps should fly the same path (within 3 m), drift=" + Num(Drift));
	}

	void TestHitchesAreStable()
	{
		FBroomFlightModel Model = MakeCruising();
		FBroomInput Input;
		Input.Throttle = 1.0;
		Input.Turn = 1.0;
		Model.Step(Input, {}, 5.0); // a 5 s hitch is clamped
		Model.Step(Input, {}, 0.0);
		Model.Step(Input, {}, -1.0);
		Expect(Finite(Model), "state must stay finite");
		Expect(Model.State.Position.Length() < 10000.0 + 0.25 * Model.Tuning.BoostSpeed * 2.0, "hitch should not teleport the broom");
	}
}

int main()
{
	const std::vector<std::pair<const char*, std::function<void()>>> Tests = {
		{ "StartsHovering", TestStartsHovering },
		{ "HoverVertical", TestHoverVertical },
		{ "HoverPitchLifts", TestHoverPitchLifts },
		{ "HoverPivot", TestHoverPivot },
		{ "ThrottleReachesMaxSpeed", TestThrottleReachesMaxSpeed },
		{ "CoastSettlesAtCruise", TestCoastSettlesAtCruise },
		{ "BrakeToHover", TestBrakeToHover },
		{ "Boost", TestBoost },
		{ "BankedTurnRight", TestBankedTurnRight },
		{ "DiveGainsSpeedClimbLoses", TestDiveGainsSpeedClimbLoses },
		{ "AutoLevel", TestAutoLevel },
		{ "GroundClearanceInDive", TestGroundClearanceInDive },
		{ "WaterSkim", TestWaterSkim },
		{ "HoverCannotSinkIntoGround", TestHoverCannotSinkIntoGround },
		{ "BoundaryTurnsBack", TestBoundaryTurnsBack },
		{ "Ceiling", TestCeiling },
		{ "Impact", TestImpact },
		{ "FrameRateIndependence", TestFrameRateIndependence },
		{ "HitchesAreStable", TestHitchesAreStable },
	};

	for (const auto& [Name, Test] : Tests)
	{
		const int Before = GFailures;
		Test();
		std::printf("[%s] %s\n", GFailures == Before ? "PASS" : "FAIL", Name);
	}

	std::printf("\n%d failure(s)\n", GFailures);
	return GFailures == 0 ? 0 : 1;
}
