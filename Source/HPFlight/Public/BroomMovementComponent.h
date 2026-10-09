#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PawnMovementComponent.h"
#include "BroomFlightModel.h"
#include "BroomMovementComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FBroomImpactSignature, float, Severity, const FHitResult&, Hit);

// Designer-facing mirror of HPFlight::FBroomTuning, in friendlier units (m/s, metres, degrees).
// Edited live in PIE: changes apply on the next tick.
USTRUCT(BlueprintType)
struct HPFLIGHT_API FBroomFlightSettings
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed", meta = (Units = "MetersPerSecond"))
	float CruiseSpeed = 25.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed", meta = (Units = "MetersPerSecond"))
	float MaxSpeed = 35.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed", meta = (Units = "MetersPerSecond"))
	float BoostSpeed = 55.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed", meta = (Units = "MetersPerSecond"))
	float TerminalSpeed = 75.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed")
	float Acceleration = 14.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed")
	float BoostAcceleration = 26.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed")
	float BrakeDeceleration = 22.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Speed", meta = (ClampMin = "0"))
	float DiveGravityScale = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hover", meta = (Units = "MetersPerSecond"))
	float HoverSpeedThreshold = 4.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hover", meta = (Units = "MetersPerSecond"))
	float HoverVerticalSpeed = 7.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handling", meta = (Units = "Degrees"))
	float MaxBankAngle = 55.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handling")
	float MaxTurnRate = 65.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handling")
	float MaxPitchRate = 75.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handling", meta = (ClampMin = "0"))
	float PitchAutoLevel = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handling", meta = (ClampMin = "0.1", ToolTip = "Lower = more drift and momentum in turns"))
	float VelocityGrip = 3.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Terrain", meta = (Units = "Meters"))
	float MinClearance = 1.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Terrain", meta = (Units = "Meters"))
	float SkimHeight = 4.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Terrain", meta = (Units = "Seconds"))
	float PullUpLeadTime = 2.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World Limits", meta = (Units = "Meters"))
	float SoftBoundaryRadius = 3000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World Limits", meta = (Units = "Meters"))
	float SoftCeiling = 700.f;

	void ApplyTo(HPFlight::FBroomTuning& Tuning) const;
};

// Broom flight for ABroomPawn. Gameplay feel lives in HPFlight::FBroomFlightModel; this component feeds it
// input and surface information, then moves the pawn with sweeps and reports collisions back.
UCLASS(ClassGroup = (HPWorld), meta = (BlueprintSpawnableComponent))
class HPFLIGHT_API UBroomMovementComponent : public UPawnMovementComponent
{
	GENERATED_BODY()

public:
	UBroomMovementComponent();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
	virtual float GetMaxSpeed() const override;

	UFUNCTION(BlueprintCallable, Category = "Broom")
	void SetFlightInput(float Pitch, float Turn, float Throttle, float Vertical, bool bBoost);

	UFUNCTION(BlueprintCallable, Category = "Broom")
	void ResetFlight(FVector Location, float Yaw);

	UFUNCTION(BlueprintPure, Category = "Broom")
	float GetSpeedAlpha() const { return static_cast<float>(Model.Telemetry.SpeedAlpha); }

	UFUNCTION(BlueprintPure, Category = "Broom")
	float GetGForce() const { return static_cast<float>(Model.Telemetry.GForce); }

	UFUNCTION(BlueprintPure, Category = "Broom")
	float GetAirspeed() const { return static_cast<float>(Model.State.Velocity.Length()); }

	UFUNCTION(BlueprintPure, Category = "Broom")
	float GetBankAngle() const { return static_cast<float>(Model.State.Roll); }

	UFUNCTION(BlueprintPure, Category = "Broom")
	bool IsHovering() const { return Model.Telemetry.bHovering; }

	UFUNCTION(BlueprintPure, Category = "Broom")
	bool IsBoosting() const { return Model.Telemetry.bBoosting; }

	UFUNCTION(BlueprintPure, Category = "Broom")
	bool IsDiving() const { return Model.Telemetry.bDiving; }

	UFUNCTION(BlueprintPure, Category = "Broom")
	bool IsSkimming() const { return Model.Telemetry.bSkimming; }

	UFUNCTION(BlueprintPure, Category = "Broom")
	bool IsSkimmingWater() const { return Model.Telemetry.bSkimmingWater; }

	UFUNCTION(BlueprintPure, Category = "Broom")
	bool IsOutsideBoundary() const { return Model.Telemetry.bOutsideBoundary; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Broom")
	FBroomFlightSettings Settings;

	// Actors or components carrying this tag count as water for skimming effects.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Broom")
	FName WaterTag = TEXT("Water");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Broom", meta = (Units = "Meters"))
	float SurfaceTraceLength = 200.f;

	UPROPERTY(BlueprintAssignable, Category = "Broom")
	FBroomImpactSignature OnBroomImpact;

private:
	void TraceSurface(HPFlight::FBroomEnvironment& OutEnvironment) const;

	HPFlight::FBroomFlightModel Model;
	HPFlight::FBroomInput PendingInput;
};
