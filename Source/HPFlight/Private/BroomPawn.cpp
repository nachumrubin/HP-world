#include "BroomPawn.h"

#include "BroomMovementComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "EnhancedPlayerInput.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "NiagaraComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FName SpeedParameter(TEXT("Speed"));

	UStaticMeshComponent* CreateGreyboxPart(AActor* Owner, USceneComponent* Parent, const TCHAR* Name, UStaticMesh* Mesh,
		const FVector& Location, const FRotator& Rotation, const FVector& Scale)
	{
		UStaticMeshComponent* Part = Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Part->SetupAttachment(Parent);
		Part->SetStaticMesh(Mesh);
		Part->SetRelativeLocationAndRotation(Location, Rotation);
		Part->SetRelativeScale3D(Scale);
		Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Part->SetGenerateOverlapEvents(false);
		return Part;
	}
}

ABroomPawn::ABroomPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	Collision = CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));
	Collision->InitSphereRadius(60.f);
	Collision->SetCollisionProfileName(UCollisionProfile::Pawn_ProfileName);
	RootComponent = Collision;

	// Greybox broom and rider built from engine basic shapes; replaced by Blender art later.
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(TEXT("/Engine/BasicShapes/Cone.Cone"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));

	BroomHandle = CreateGreyboxPart(this, Collision, TEXT("BroomHandle"), CylinderMesh.Object,
		FVector(10.f, 0.f, -25.f), FRotator(90.f, 0.f, 0.f), FVector(0.06f, 0.06f, 1.9f));
	BroomBristles = CreateGreyboxPart(this, Collision, TEXT("BroomBristles"), ConeMesh.Object,
		FVector(-100.f, 0.f, -25.f), FRotator(-90.f, 0.f, 0.f), FVector(0.3f, 0.3f, 0.55f));
	RiderBody = CreateGreyboxPart(this, Collision, TEXT("RiderBody"), CylinderMesh.Object,
		FVector(-15.f, 0.f, 25.f), FRotator(-15.f, 0.f, 0.f), FVector(0.4f, 0.4f, 0.8f));
	RiderHead = CreateGreyboxPart(this, Collision, TEXT("RiderHead"), SphereMesh.Object,
		FVector(0.f, 0.f, 80.f), FRotator::ZeroRotator, FVector(0.3f));

	SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
	SpringArm->SetupAttachment(Collision);
	SpringArm->TargetArmLength = BaseArmLength;
	SpringArm->SocketOffset = FVector(0.f, 0.f, 90.f);
	SpringArm->bUsePawnControlRotation = false;
	SpringArm->bInheritRoll = false; // the camera banks only partially, in UpdateCamera
	SpringArm->bEnableCameraLag = true;
	SpringArm->CameraLagSpeed = 10.f;
	SpringArm->bEnableCameraRotationLag = true;
	SpringArm->CameraRotationLagSpeed = 7.f;
	SpringArm->ProbeSize = 12.f;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(SpringArm, USpringArmComponent::SocketName);
	Camera->SetFieldOfView(BaseFieldOfView);

	BroomMovement = CreateDefaultSubobject<UBroomMovementComponent>(TEXT("BroomMovement"));
	BroomMovement->UpdatedComponent = Collision;

	WindAudio = CreateDefaultSubobject<UAudioComponent>(TEXT("WindAudio"));
	WindAudio->SetupAttachment(Camera);
	WindAudio->bAutoActivate = false;

	SpeedStreaks = CreateDefaultSubobject<UNiagaraComponent>(TEXT("SpeedStreaks"));
	SpeedStreaks->SetupAttachment(Camera);
	SpeedStreaks->SetRelativeLocation(FVector(300.f, 0.f, 0.f));
	SpeedStreaks->bAutoActivate = false;

	WaterWake = CreateDefaultSubobject<UNiagaraComponent>(TEXT("WaterWake"));
	WaterWake->SetupAttachment(Collision);
	WaterWake->SetRelativeLocation(FVector(-60.f, 0.f, -150.f));
	WaterWake->bAutoActivate = false;
}

UPawnMovementComponent* ABroomPawn::GetMovementComponent() const
{
	return BroomMovement;
}

void ABroomPawn::BeginPlay()
{
	Super::BeginPlay();

	StartTransform = GetActorTransform();
	BroomMovement->OnBroomImpact.AddDynamic(this, &ABroomPawn::HandleBroomImpact);

	if (WindAudio->Sound)
	{
		WindAudio->Play();
	}
}

void ABroomPawn::BuildDefaultInput()
{
	if (InputMapping)
	{
		return;
	}

	auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = Type;
		return Action;
	};

	PitchAction = MakeAction(TEXT("IA_BroomPitch"), EInputActionValueType::Axis1D);
	TurnAction = MakeAction(TEXT("IA_BroomTurn"), EInputActionValueType::Axis1D);
	MousePitchAction = MakeAction(TEXT("IA_BroomMousePitch"), EInputActionValueType::Axis1D);
	MouseTurnAction = MakeAction(TEXT("IA_BroomMouseTurn"), EInputActionValueType::Axis1D);
	ThrottleAction = MakeAction(TEXT("IA_BroomThrottle"), EInputActionValueType::Axis1D);
	VerticalAction = MakeAction(TEXT("IA_BroomVertical"), EInputActionValueType::Axis1D);
	BoostAction = MakeAction(TEXT("IA_BroomBoost"), EInputActionValueType::Boolean);
	LookYawAction = MakeAction(TEXT("IA_BroomLookYaw"), EInputActionValueType::Axis1D);
	LookPitchAction = MakeAction(TEXT("IA_BroomLookPitch"), EInputActionValueType::Axis1D);
	ResetAction = MakeAction(TEXT("IA_BroomReset"), EInputActionValueType::Boolean);

	UInputMappingContext* Mapping = NewObject<UInputMappingContext>(this, TEXT("IMC_BroomDefault"));
	auto Map = [Mapping](UInputAction* Action, const FKey& Key, bool bNegate = false, bool bDeadZone = false)
	{
		FEnhancedActionKeyMapping& KeyMapping = Mapping->MapKey(Action, Key);
		if (bDeadZone)
		{
			KeyMapping.Modifiers.Add(NewObject<UInputModifierDeadZone>(Mapping));
		}
		if (bNegate)
		{
			KeyMapping.Modifiers.Add(NewObject<UInputModifierNegate>(Mapping));
		}
	};

	// Keyboard + mouse: mouse steers, W/S throttle & brake, Space/Ctrl hover up/down, Shift boost.
	Map(MouseTurnAction, EKeys::MouseX);
	Map(MousePitchAction, EKeys::MouseY);
	Map(TurnAction, EKeys::D);
	Map(TurnAction, EKeys::A, true);
	Map(PitchAction, EKeys::Up);
	Map(PitchAction, EKeys::Down, true);
	Map(TurnAction, EKeys::Right);
	Map(TurnAction, EKeys::Left, true);
	Map(ThrottleAction, EKeys::W);
	Map(ThrottleAction, EKeys::S, true);
	Map(VerticalAction, EKeys::SpaceBar);
	Map(VerticalAction, EKeys::LeftControl, true);
	Map(BoostAction, EKeys::LeftShift);
	Map(ResetAction, EKeys::R);

	// Gamepad: left stick flies, triggers throttle/brake, A/B hover up/down, L3 or RB boost, right stick looks around.
	Map(TurnAction, EKeys::Gamepad_LeftX, false, true);
	Map(PitchAction, EKeys::Gamepad_LeftY, false, true);
	Map(ThrottleAction, EKeys::Gamepad_RightTriggerAxis);
	Map(ThrottleAction, EKeys::Gamepad_LeftTriggerAxis, true);
	Map(VerticalAction, EKeys::Gamepad_FaceButton_Bottom);
	Map(VerticalAction, EKeys::Gamepad_FaceButton_Right, true);
	Map(BoostAction, EKeys::Gamepad_LeftThumbstick);
	Map(BoostAction, EKeys::Gamepad_RightShoulder);
	Map(LookYawAction, EKeys::Gamepad_RightX, false, true);
	Map(LookPitchAction, EKeys::Gamepad_RightY, false, true);
	Map(ResetAction, EKeys::Gamepad_Special_Left);

	InputMapping = Mapping;
}

void ABroomPawn::PawnClientRestart()
{
	Super::PawnClientRestart();

	BuildDefaultInput();
	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Subsystem->ClearAllMappings();
			Subsystem->AddMappingContext(InputMapping, 0);
		}
	}
}

void ABroomPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	BuildDefaultInput();
	if (UEnhancedInputComponent* EnhancedInput = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		if (ResetAction)
		{
			EnhancedInput->BindAction(ResetAction, ETriggerEvent::Started, this, &ABroomPawn::ResetToStart);
		}
	}
	// Flight axes are polled every tick in UpdateInput.
}

float ABroomPawn::ReadAxis(const UInputAction* Action) const
{
	if (!Action)
	{
		return 0.f;
	}
	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (const UEnhancedPlayerInput* PlayerInput = Cast<UEnhancedPlayerInput>(PC->PlayerInput))
		{
			return PlayerInput->GetActionValue(Action).Get<float>();
		}
	}
	return 0.f;
}

void ABroomPawn::ResetToStart()
{
	BroomMovement->ResetFlight(StartTransform.GetLocation(), StartTransform.Rotator().Yaw);
	MouseStick = FVector2D::ZeroVector;
	FreeLook = FRotator::ZeroRotator;
}

void ABroomPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UpdateInput(DeltaSeconds);
	UpdateCamera(DeltaSeconds);
	UpdateEffects();
}

void ABroomPawn::UpdateInput(float DeltaSeconds)
{
	// Mouse deltas push a virtual stick that relaxes back to centre, so mouse flying feels like holding a stick.
	MouseStick.X = FMath::Clamp(MouseStick.X + ReadAxis(MouseTurnAction) * MouseSensitivity, -1.f, 1.f);
	MouseStick.Y = FMath::Clamp(MouseStick.Y + ReadAxis(MousePitchAction) * MouseSensitivity, -1.f, 1.f);
	MouseStick *= FMath::Exp(-MouseStickReturn * DeltaSeconds);

	const float StickPitch = ReadAxis(PitchAction) * (bInvertStickPitch ? -1.f : 1.f);
	const float MousePitch = MouseStick.Y * (bInvertMousePitch ? -1.f : 1.f);

	BroomMovement->SetFlightInput(
		FMath::Clamp(StickPitch + MousePitch, -1.f, 1.f),
		FMath::Clamp(ReadAxis(TurnAction) + MouseStick.X, -1.f, 1.f),
		ReadAxis(ThrottleAction),
		ReadAxis(VerticalAction),
		ReadAxis(BoostAction) > 0.5f);
}

void ABroomPawn::UpdateCamera(float DeltaSeconds)
{
	SmoothedSpeedAlpha = FMath::FInterpTo(SmoothedSpeedAlpha, BroomMovement->GetSpeedAlpha(), DeltaSeconds, 3.f);
	const float Speed = SmoothedSpeedAlpha;

	Camera->SetFieldOfView(FMath::Lerp(BaseFieldOfView, MaxFieldOfView, FMath::Pow(Speed, 1.3f) * MotionIntensity));
	SpringArm->TargetArmLength = FMath::Lerp(BaseArmLength, SpeedArmLength, Speed);

	// Free look on the right stick; springs back when released.
	const FRotator LookTarget(ReadAxis(LookPitchAction) * FreeLookRange * 0.5f, ReadAxis(LookYawAction) * FreeLookRange, 0.f);
	FreeLook = FMath::RInterpTo(FreeLook, LookTarget, DeltaSeconds, 6.f);
	SpringArm->SetRelativeRotation(FRotator(-10.f + FreeLook.Pitch, FreeLook.Yaw, 0.f));

	// Shake: hard G (turns, pull-ups), very high speed, and impacts.
	ImpactShake = FMath::FInterpTo(ImpactShake, 0.f, DeltaSeconds, 4.f);
	const float GShake = FMath::Clamp((BroomMovement->GetGForce() - 2.f) / 4.f, 0.f, 1.f) * 0.5f;
	const float SpeedShake = FMath::Clamp((Speed - 0.75f) * 4.f, 0.f, 1.f) * 0.35f;
	const float Shake = FMath::Max3(GShake, SpeedShake, ImpactShake) * ShakeStrength * MotionIntensity;

	ShakeTime += DeltaSeconds;
	const float Frequency = 9.f + 12.f * Speed;
	const FVector ShakeOffset(0.f,
		FMath::PerlinNoise1D(ShakeTime * Frequency) * 6.f * Shake,
		FMath::PerlinNoise1D(ShakeTime * Frequency + 37.f) * 6.f * Shake);
	const float ShakeRoll = FMath::PerlinNoise1D(ShakeTime * Frequency + 71.f) * 1.5f * Shake;

	Camera->SetRelativeLocationAndRotation(ShakeOffset,
		FRotator(0.f, 0.f, BroomMovement->GetBankAngle() * CameraBankFactor + ShakeRoll));
}

void ABroomPawn::UpdateEffects()
{
	const float Speed = SmoothedSpeedAlpha;

	// Post-process speed cues that need no assets: chromatic fringing and a tighter vignette.
	FPostProcessSettings& PP = Camera->PostProcessSettings;
	PP.bOverride_SceneFringeIntensity = true;
	PP.SceneFringeIntensity = FMath::Clamp((Speed - 0.4f) * 5.f, 0.f, 3.f) * MotionIntensity;
	PP.bOverride_VignetteIntensity = true;
	PP.VignetteIntensity = 0.4f + 0.4f * Speed * MotionIntensity;

	if (WindAudio->Sound)
	{
		WindAudio->SetVolumeMultiplier(FMath::Lerp(0.08f, 1.f, Speed));
		WindAudio->SetPitchMultiplier(FMath::Lerp(0.8f, 1.35f, Speed));
		WindAudio->SetFloatParameter(SpeedParameter, Speed);
	}

	if (SpeedStreaks->GetAsset())
	{
		SpeedStreaks->SetVariableFloat(SpeedParameter, Speed);
		const bool bWantStreaks = Speed > 0.35f;
		if (bWantStreaks != SpeedStreaks->IsActive())
		{
			SpeedStreaks->SetActive(bWantStreaks);
		}
	}

	if (WaterWake->GetAsset())
	{
		const bool bWantWake = BroomMovement->IsSkimmingWater() && !BroomMovement->IsHovering();
		if (bWantWake != WaterWake->IsActive())
		{
			WaterWake->SetActive(bWantWake);
		}
	}
}

void ABroomPawn::HandleBroomImpact(float Severity, const FHitResult& Hit)
{
	ImpactShake = FMath::Max(ImpactShake, FMath::Clamp(Severity * 1.5f, 0.f, 1.f));
}
