#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "BroomPawn.generated.h"

class UAudioComponent;
class UBroomMovementComponent;
class UCameraComponent;
class UInputAction;
class UInputMappingContext;
class UNiagaraComponent;
class USphereComponent;
class USpringArmComponent;
class UStaticMeshComponent;

// The player on a broom. Owns the chase camera and the speed effects; all flight lives in UBroomMovementComponent.
//
// Input: if InputMapping is left empty, a default keyboard/mouse + gamepad mapping is built at runtime so the
// prototype runs without any input assets. Assign your own mapping context and actions in a Blueprint subclass
// to override it.
UCLASS()
class HPFLIGHT_API ABroomPawn : public APawn
{
	GENERATED_BODY()

public:
	ABroomPawn();

	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;
	virtual UPawnMovementComponent* GetMovementComponent() const override;

	UFUNCTION(BlueprintCallable, Category = "Broom")
	void ResetToStart();

protected:
	virtual void BeginPlay() override;

	// --- Components ---

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USphereComponent> Collision;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> BroomHandle;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> BroomBristles;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> RiderBody;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> RiderHead;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USpringArmComponent> SpringArm;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UBroomMovementComponent> BroomMovement;

	// Looping wind sound. Volume and pitch follow speed; a "Speed" (0..1) float parameter is also set for MetaSounds.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UAudioComponent> WindAudio;

	// Speed-line streaks around the camera. Receives a "Speed" (0..1) user float.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UNiagaraComponent> SpeedStreaks;

	// Spray/wake under the broom while skimming water.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UNiagaraComponent> WaterWake;

	// --- Input ---

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputMappingContext> InputMapping;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> PitchAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> TurnAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> MousePitchAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> MouseTurnAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> ThrottleAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> VerticalAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> BoostAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> LookYawAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> LookPitchAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> ResetAction;

	// Flight-sim style: pushing the stick (or Up arrow) forward dives.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Input")
	bool bInvertStickPitch = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Input")
	bool bInvertMousePitch = false;

	// Mouse movement nudges a virtual stick that springs back to centre.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Input")
	float MouseSensitivity = 0.04f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Input")
	float MouseStickReturn = 3.f;

	// --- Camera feel ---

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
	float BaseFieldOfView = 80.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
	float MaxFieldOfView = 105.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
	float BaseArmLength = 420.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
	float SpeedArmLength = 560.f;

	// How much of the broom's bank the camera follows (0 = horizon locked, 1 = fully rolled).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera", meta = (ClampMin = "0", ClampMax = "1"))
	float CameraBankFactor = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera", meta = (Units = "Degrees"))
	float FreeLookRange = 110.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
	float ShakeStrength = 1.f;

	// Accessibility: scales FOV widening, shake and chromatic aberration.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera", meta = (ClampMin = "0", ClampMax = "1"))
	float MotionIntensity = 1.f;

private:
	void BuildDefaultInput();
	float ReadAxis(const UInputAction* Action) const;
	void UpdateInput(float DeltaSeconds);
	void UpdateCamera(float DeltaSeconds);
	void UpdateEffects();

	UFUNCTION()
	void HandleBroomImpact(float Severity, const FHitResult& Hit);

	FVector2D MouseStick = FVector2D::ZeroVector;
	FRotator FreeLook = FRotator::ZeroRotator;
	float SmoothedSpeedAlpha = 0.f;
	float ImpactShake = 0.f;
	float ShakeTime = 0.f;
	FTransform StartTransform;
};
