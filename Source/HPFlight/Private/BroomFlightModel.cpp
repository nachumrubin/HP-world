#include "BroomFlightModel.h"

#include <algorithm>
#include <cmath>

namespace HPFlight
{
	namespace
	{
		constexpr double kDegToRad = 3.14159265358979323846 / 180.0;
		constexpr double kRadToDeg = 180.0 / 3.14159265358979323846;
		constexpr double kNoSurface = 1.0e8;

		// Frame-rate independent exponential approach factor.
		double Blend(double Rate, double Dt)
		{
			return 1.0 - std::exp(-Rate * Dt);
		}

		double Clamp01(double V)
		{
			return std::clamp(V, 0.0, 1.0);
		}

		double SmoothStep(double Edge0, double Edge1, double X)
		{
			const double T = Clamp01((X - Edge0) / (Edge1 - Edge0));
			return T * T * (3.0 - 2.0 * T);
		}

		double WrapDegrees(double Angle)
		{
			Angle = std::fmod(Angle + 180.0, 360.0);
			if (Angle < 0.0)
			{
				Angle += 360.0;
			}
			return Angle - 180.0;
		}
	}

	double FFlightVec::Length() const
	{
		return std::sqrt(X * X + Y * Y + Z * Z);
	}

	void FBroomFlightModel::Reset(const FFlightVec& Position, double Yaw)
	{
		State = FBroomState();
		State.Position = Position;
		State.Yaw = WrapDegrees(Yaw);
		Telemetry = FBroomTelemetry();
	}

	FFlightVec FBroomFlightModel::GetForward() const
	{
		const double P = State.Pitch * kDegToRad;
		const double Y = State.Yaw * kDegToRad;
		return { std::cos(P) * std::cos(Y), std::cos(P) * std::sin(Y), std::sin(P) };
	}

	void FBroomFlightModel::Step(const FBroomInput& RawInput, const FBroomEnvironment& Environment, double DeltaSeconds)
	{
		if (!(DeltaSeconds > 0.0))
		{
			return;
		}
		// Ignore long hitches (loading, breakpoints) rather than teleporting the player.
		DeltaSeconds = std::min(DeltaSeconds, 0.25);

		FBroomInput Input = RawInput;
		Input.Pitch = std::clamp(Input.Pitch, -1.0, 1.0);
		Input.Turn = std::clamp(Input.Turn, -1.0, 1.0);
		Input.Throttle = std::clamp(Input.Throttle, -1.0, 1.0);
		Input.Vertical = std::clamp(Input.Vertical, -1.0, 1.0);

		const int NumSteps = std::max(1, static_cast<int>(std::ceil(DeltaSeconds / Tuning.MaxSubstep)));
		const double Dt = DeltaSeconds / NumSteps;
		const double StartZ = State.Position.Z;

		for (int Index = 0; Index < NumSteps; ++Index)
		{
			// The surface height was sampled at the start of the frame; track our own vertical motion since.
			FBroomEnvironment Local = Environment;
			if (Local.HeightAboveSurface < kNoSurface)
			{
				Local.HeightAboveSurface += State.Position.Z - StartZ;
			}
			Substep(Input, Local, Dt);
		}
	}

	void FBroomFlightModel::Substep(const FBroomInput& Input, const FBroomEnvironment& Environment, double Dt)
	{
		const double HoverBlend = 1.0 - SmoothStep(0.5 * Tuning.HoverSpeedThreshold, Tuning.HoverSpeedThreshold, State.Speed);
		const double Height = Environment.HeightAboveSurface;

		UpdateSpeed(Input, HoverBlend, Dt);
		UpdateAttitude(Input, HoverBlend, Dt);

		// Close to the ground or water the nose is gently lifted: an automatic dive pull-up. It starts early
		// when descending fast (by time to impact) so a full-speed dive becomes a swoop, not a slam.
		const double Clearance = Height - Tuning.MinClearance;
		const double HeightProximity = Clamp01(1.0 - Clearance / (2.0 * Tuning.SkimHeight));
		const double DescentRate = std::max(-State.Velocity.Z, 1.0);
		const double TimeToImpact = std::max(Clearance, 0.0) / DescentRate;
		const double ImpactProximity = Clamp01(1.0 - (TimeToImpact - Tuning.PullUpLeadTime * 0.2) / (Tuning.PullUpLeadTime * 0.8));
		const double Proximity = std::max(HeightProximity, ImpactProximity);
		if (State.Pitch < 0.0 && Proximity > 0.0)
		{
			State.Pitch -= State.Pitch * Blend(Tuning.ClearanceStiffness * Proximity, Dt);
		}

		const FFlightVec Previous = State.Velocity;
		FFlightVec Desired = GetForward() * State.Speed;
		// When hovering, pitching up/down also rises/sinks, so the stick does something useful from a standstill.
		const double Lift = std::clamp(Input.Vertical + Input.Pitch, -1.0, 1.0);
		Desired.Z += Lift * Tuning.HoverVerticalSpeed * HoverBlend;

		// Velocity lags the nose a little, which gives the broom momentum and drift in turns.
		const double Grip = Tuning.VelocityGrip * (1.0 + 2.0 * HoverBlend);
		State.Velocity += (Desired - State.Velocity) * Blend(Grip, Dt);

		// Soft floor: allowed descent rate shrinks as we approach MinClearance, and below it we are pushed up.
		if (Height < kNoSurface)
		{
			const double MinVerticalSpeed = (Tuning.MinClearance - Height) * Tuning.ClearanceStiffness;
			State.Velocity.Z = std::max(State.Velocity.Z, MinVerticalSpeed);
		}

		ApplyWorldLimits(Dt);

		State.Position += State.Velocity * Dt;

		// Telemetry.
		FFlightVec Accel = (State.Velocity - Previous) * (1.0 / Dt);
		Accel.Z += Tuning.Gravity;
		const double InstantG = Accel.Length() / Tuning.Gravity;
		Telemetry.GForce += (InstantG - Telemetry.GForce) * Blend(5.0, Dt);
		Telemetry.SpeedAlpha = Clamp01(State.Velocity.Length() / Tuning.BoostSpeed);
		Telemetry.bHovering = State.Speed < Tuning.HoverSpeedThreshold;
		Telemetry.bBoosting = Input.bBoost && !Telemetry.bHovering;
		Telemetry.bDiving = State.Pitch < -25.0 && State.Velocity.Z < -1000.0;
		Telemetry.bSkimming = Height < Tuning.SkimHeight;
		Telemetry.bSkimmingWater = Telemetry.bSkimming && Environment.bSurfaceIsWater;
	}

	void FBroomFlightModel::UpdateSpeed(const FBroomInput& Input, double HoverBlend, double Dt)
	{
		double Throttle = Input.Throttle;
		if (Input.bBoost)
		{
			Throttle = std::max(Throttle, 1.0);
		}
		const double TopSpeed = Input.bBoost ? Tuning.BoostSpeed : Tuning.MaxSpeed;
		const double Accel = Input.bBoost ? Tuning.BoostAcceleration : Tuning.Acceleration;

		if (Throttle > 0.0)
		{
			if (State.Speed < TopSpeed)
			{
				State.Speed = std::min(TopSpeed, State.Speed + Throttle * Accel * Dt);
			}
		}
		else if (Throttle < 0.0)
		{
			State.Speed = std::max(0.0, State.Speed + Throttle * Tuning.BrakeDeceleration * Dt);
		}
		else
		{
			// Coasting: settle at cruise speed, or come to a hover if we were already slow.
			const double Target = State.Speed >= Tuning.HoverSpeedThreshold ? Tuning.CruiseSpeed : 0.0;
			State.Speed += (Target - State.Speed) * Blend(Tuning.CoastResponse, Dt);
		}

		// Diving trades height for speed, climbing bleeds it.
		const double Fly = 1.0 - HoverBlend;
		State.Speed -= std::sin(State.Pitch * kDegToRad) * Tuning.Gravity * Tuning.DiveGravityScale * Fly * Dt;

		if (State.Speed > TopSpeed)
		{
			State.Speed -= (State.Speed - TopSpeed) * Blend(Tuning.OverspeedDrag, Dt);
		}
		State.Speed = std::clamp(State.Speed, 0.0, Tuning.TerminalSpeed);
	}

	void FBroomFlightModel::UpdateAttitude(const FBroomInput& Input, double HoverBlend, double Dt)
	{
		const double Fly = 1.0 - HoverBlend;

		// Bank into turns; a hovering broom only leans slightly.
		const double TargetRoll = Input.Turn * Tuning.MaxBankAngle * (0.25 + 0.75 * Fly);
		State.Roll += (TargetRoll - State.Roll) * Blend(Tuning.BankResponse, Dt);

		// In flight, yaw comes from bank (coordinated turn). When hovering the broom pivots on the spot.
		const double YawRate = (State.Roll / Tuning.MaxBankAngle) * Tuning.MaxTurnRate * Fly
			+ Input.Turn * Tuning.HoverYawRate * HoverBlend;
		State.Yaw = WrapDegrees(State.Yaw + YawRate * Dt);

		if (std::abs(Input.Pitch) > 0.05)
		{
			State.Pitch += Input.Pitch * Tuning.MaxPitchRate * Fly * Dt;
		}
		else
		{
			State.Pitch -= State.Pitch * Blend(Tuning.PitchAutoLevel, Dt);
		}
		if (HoverBlend > 0.0)
		{
			State.Pitch -= State.Pitch * Blend(3.0 * HoverBlend, Dt);
		}
		State.Pitch = std::clamp(State.Pitch, -Tuning.MaxPitchAngle, Tuning.MaxPitchAngle);
	}

	void FBroomFlightModel::ApplyWorldLimits(double Dt)
	{
		// Horizontal boundary: a magical wind gently turns the broom back toward the castle.
		const double Radius = std::sqrt(State.Position.X * State.Position.X + State.Position.Y * State.Position.Y);
		Telemetry.bOutsideBoundary = Radius > Tuning.SoftBoundaryRadius;
		if (Telemetry.bOutsideBoundary)
		{
			const double Excess = Clamp01((Radius - Tuning.SoftBoundaryRadius) / Tuning.BoundaryFadeWidth);
			const double YawToCentre = std::atan2(-State.Position.Y, -State.Position.X) * kRadToDeg;
			const double Diff = WrapDegrees(YawToCentre - State.Yaw);
			const double MaxTurn = Tuning.BoundaryTurnRate * std::max(Excess, 0.2) * Dt;
			State.Yaw = WrapDegrees(State.Yaw + std::clamp(Diff, -MaxTurn, MaxTurn));

			// Hard stop at the far edge of the fade: no outward motion.
			const double HardRadius = Tuning.SoftBoundaryRadius + Tuning.BoundaryFadeWidth;
			if (Radius >= HardRadius)
			{
				const FFlightVec Outward(State.Position.X / Radius, State.Position.Y / Radius, 0.0);
				const double OutwardSpeed = State.Velocity.Dot(Outward);
				if (OutwardSpeed > 0.0)
				{
					State.Velocity = State.Velocity - Outward * OutwardSpeed;
				}
			}
		}

		// Ceiling: the air thins, the nose drops, and climbing stops at the top of the fade.
		if (State.Position.Z > Tuning.SoftCeiling)
		{
			const double Excess = Clamp01((State.Position.Z - Tuning.SoftCeiling) / Tuning.CeilingFadeHeight);
			if (State.Pitch > -15.0)
			{
				State.Pitch += (-15.0 - State.Pitch) * Blend(2.0 * Excess, Dt);
			}
			const double HardCeiling = Tuning.SoftCeiling + Tuning.CeilingFadeHeight;
			State.Velocity.Z = std::min(State.Velocity.Z, (HardCeiling - State.Position.Z) * 2.0);
		}
	}

	double FBroomFlightModel::ApplyImpact(const FFlightVec& SurfaceNormal)
	{
		const double NormalLength = SurfaceNormal.Length();
		if (NormalLength <= 0.0)
		{
			return 0.0;
		}
		const FFlightVec N = SurfaceNormal * (1.0 / NormalLength);
		const double IntoSurface = State.Velocity.Dot(N);
		if (IntoSurface >= 0.0)
		{
			return 0.0;
		}

		const double SpeedBefore = std::max(State.Velocity.Length(), 1.0);
		const double Directness = Clamp01(-IntoSurface / SpeedBefore);
		State.Velocity = State.Velocity - N * IntoSurface;
		State.Speed *= 1.0 - 0.7 * Directness;

		return Clamp01(-IntoSurface / Tuning.MaxSpeed);
	}
}
