#include "BroomMovementComponent.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Components/PrimitiveComponent.h"

namespace
{
	HPFlight::FFlightVec ToFlight(const FVector& V)
	{
		return { V.X, V.Y, V.Z };
	}

	FVector ToUnreal(const HPFlight::FFlightVec& V)
	{
		return FVector(V.X, V.Y, V.Z);
	}

	constexpr double MetresToCm = 100.0;
}

void FBroomFlightSettings::ApplyTo(HPFlight::FBroomTuning& Tuning) const
{
	Tuning.CruiseSpeed = CruiseSpeed * MetresToCm;
	Tuning.MaxSpeed = MaxSpeed * MetresToCm;
	Tuning.BoostSpeed = BoostSpeed * MetresToCm;
	Tuning.TerminalSpeed = TerminalSpeed * MetresToCm;
	Tuning.Acceleration = Acceleration * MetresToCm;
	Tuning.BoostAcceleration = BoostAcceleration * MetresToCm;
	Tuning.BrakeDeceleration = BrakeDeceleration * MetresToCm;
	Tuning.DiveGravityScale = DiveGravityScale;
	Tuning.HoverSpeedThreshold = HoverSpeedThreshold * MetresToCm;
	Tuning.HoverVerticalSpeed = HoverVerticalSpeed * MetresToCm;
	Tuning.MaxBankAngle = FMath::Max(MaxBankAngle, 1.f);
	Tuning.MaxTurnRate = MaxTurnRate;
	Tuning.MaxPitchRate = MaxPitchRate;
	Tuning.PitchAutoLevel = PitchAutoLevel;
	Tuning.VelocityGrip = FMath::Max(VelocityGrip, 0.1f);
	Tuning.MinClearance = MinClearance * MetresToCm;
	Tuning.SkimHeight = SkimHeight * MetresToCm;
	Tuning.PullUpLeadTime = FMath::Max(PullUpLeadTime, 0.1f);
	Tuning.SoftBoundaryRadius = SoftBoundaryRadius * MetresToCm;
	Tuning.SoftCeiling = SoftCeiling * MetresToCm;
}

UBroomMovementComponent::UBroomMovementComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	bConstrainToPlane = false;
}

void UBroomMovementComponent::BeginPlay()
{
	Super::BeginPlay();

	Settings.ApplyTo(Model.Tuning);
	if (UpdatedComponent)
	{
		ResetFlight(UpdatedComponent->GetComponentLocation(), UpdatedComponent->GetComponentRotation().Yaw);
	}
}

float UBroomMovementComponent::GetMaxSpeed() const
{
	return static_cast<float>(Model.Tuning.TerminalSpeed);
}

void UBroomMovementComponent::SetFlightInput(float Pitch, float Turn, float Throttle, float Vertical, bool bBoost)
{
	PendingInput.Pitch = Pitch;
	PendingInput.Turn = Turn;
	PendingInput.Throttle = Throttle;
	PendingInput.Vertical = Vertical;
	PendingInput.bBoost = bBoost;
}

void UBroomMovementComponent::ResetFlight(FVector Location, float Yaw)
{
	Model.Reset(ToFlight(Location), Yaw);
	if (UpdatedComponent)
	{
		UpdatedComponent->SetWorldLocationAndRotation(Location, FRotator(0.f, Yaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	}
	Velocity = FVector::ZeroVector;
}

void UBroomMovementComponent::TraceSurface(HPFlight::FBroomEnvironment& OutEnvironment) const
{
	UWorld* World = GetWorld();
	if (!World || !UpdatedComponent)
	{
		return;
	}

	const FVector Start = UpdatedComponent->GetComponentLocation();
	const FVector End = Start - FVector(0.f, 0.f, SurfaceTraceLength * MetresToCm);

	FCollisionQueryParams Params(SCENE_QUERY_STAT(BroomSurfaceTrace), false, GetOwner());
	FHitResult Hit;
	if (World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
	{
		// Measure from the bottom of the collision shape, not its centre.
		const double HalfHeight = UpdatedComponent->Bounds.BoxExtent.Z;
		OutEnvironment.HeightAboveSurface = FMath::Max(0.0, static_cast<double>(Hit.Distance) - HalfHeight);

		const AActor* HitActor = Hit.GetActor();
		const UPrimitiveComponent* HitComponent = Hit.GetComponent();
		OutEnvironment.bSurfaceIsWater = (HitActor && HitActor->ActorHasTag(WaterTag))
			|| (HitComponent && HitComponent->ComponentHasTag(WaterTag));
	}
}

void UBroomMovementComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (!PawnOwner || !UpdatedComponent || ShouldSkipUpdate(DeltaTime))
	{
		return;
	}

	Settings.ApplyTo(Model.Tuning);

	HPFlight::FBroomEnvironment Environment;
	TraceSurface(Environment);

	const FVector OldLocation = UpdatedComponent->GetComponentLocation();
	Model.State.Position = ToFlight(OldLocation);
	Model.Step(PendingInput, Environment, DeltaTime);

	const FVector Delta = ToUnreal(Model.State.Position) - OldLocation;
	const FQuat NewRotation = FRotator(Model.State.Pitch, Model.State.Yaw, Model.State.Roll).Quaternion();

	FHitResult Hit;
	SafeMoveUpdatedComponent(Delta, NewRotation, true, Hit);
	if (Hit.IsValidBlockingHit())
	{
		const double Severity = Model.ApplyImpact(ToFlight(Hit.Normal));
		SlideAlongSurface(Delta, 1.f - Hit.Time, Hit.Normal, Hit, true);
		if (Severity > 0.0)
		{
			OnBroomImpact.Broadcast(static_cast<float>(Severity), Hit);
		}
	}

	// The sweep is the authority on where we ended up.
	Model.State.Position = ToFlight(UpdatedComponent->GetComponentLocation());
	Velocity = ToUnreal(Model.State.Velocity);
	UpdateComponentVelocity();
}
