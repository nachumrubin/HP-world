#include "HPFlightGameMode.h"

#include "BroomPawn.h"
#include "BroomMovementComponent.h"
#include "Camera/CameraActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Kismet/KismetMathLibrary.h"
#include "TimerManager.h"

namespace
{
	struct FShotSpec
	{
		const TCHAR* Name;
		FVector Location;
		FVector Target;
	};

	// Same viewpoints as the old Tools/Unreal/render_shots_m1.py, in cm.
	const FShotSpec GShots[] = {
		{TEXT("castle_300m_south"), FVector(0, -90000, 30000), FVector(0, 0, 8000)},
		{TEXT("castle_150m_close"), FVector(-12000, -20000, 15000), FVector(0, 0, 8000)},
		{TEXT("overview_1500m"), FVector(0, -250000, 150000), FVector(0, 0, 5000)},
		{TEXT("topdown_6km"), FVector(0, 0, 600000), FVector(0, 0, 0)},
		{TEXT("hogsmeade_hill"), FVector(110000, -150000, 25000), FVector(156000, -223500, 6500)},
		{TEXT("station_train"), FVector(-10000, -120000, 12000), FVector(-38000, -156000, 3500)},
		{TEXT("lake_waterfall"), FVector(-20000, -90000, 9000), FVector(0, -24000, 3500)},
		{TEXT("river_forest"), FVector(-60000, 15000, 14000), FVector(-30000, 80000, 500)},
		{TEXT("castle_top"), FVector(100, 100, 90000), FVector(0, 0, 12000)},
		{TEXT("castle_north"), FVector(75000, 0, 30000), FVector(0, 0, 14000)},
		{TEXT("castle_east"), FVector(0, 75000, 30000), FVector(0, 0, 14000)},
		{TEXT("castle_west"), FVector(0, -75000, 30000), FVector(0, 0, 14000)},
	};
}

AHPFlightGameMode::AHPFlightGameMode()
{
	PrimaryActorTick.bCanEverTick = true;
	DefaultPawnClass = ABroomPawn::StaticClass();
}

void AHPFlightGameMode::BeginPlay()
{
	Super::BeginPlay();
	bAutoFly = FParse::Param(FCommandLine::Get(), TEXT("HPAutoFly"));
	if (FParse::Param(FCommandLine::Get(), TEXT("HPShots")))
	{
		StartScreenshotRun();
	}
}

void AHPFlightGameMode::StartScreenshotRun()
{
	// Give shaders and landscape/mesh streaming time to settle before the first shot.
	GetWorldTimerManager().SetTimer(ShotTimer, this, &AHPFlightGameMode::NextScreenshot, 60.0f, false);
}

void AHPFlightGameMode::NextScreenshot()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC)
	{
		return;
	}

	if (bShotPending)
	{
		const FShotSpec& Prev = GShots[ShotIndex];
		const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("Tools/generated/shots") / (FString(Prev.Name) + TEXT(".png")));
		PC->ConsoleCommand(FString::Printf(TEXT("HighResShot 1600x900 filename=\"%s\""), *Path));
		bShotPending = false;
		++ShotIndex;
		GetWorldTimerManager().SetTimer(ShotTimer, this, &AHPFlightGameMode::NextScreenshot, 5.0f, false);
		return;
	}

	if (ShotIndex >= UE_ARRAY_COUNT(GShots))
	{
		PC->ConsoleCommand(TEXT("quit"));
		return;
	}

	const FShotSpec& Spec = GShots[ShotIndex];
	if (!ShotCamera.IsValid())
	{
		ShotCamera = GetWorld()->SpawnActor<ACameraActor>();
	}
	ShotCamera->SetActorLocationAndRotation(Spec.Location, UKismetMathLibrary::FindLookAtRotation(Spec.Location, Spec.Target));
	PC->SetViewTarget(ShotCamera.Get());
	bShotPending = true;
	GetWorldTimerManager().SetTimer(ShotTimer, this, &AHPFlightGameMode::NextScreenshot, 15.0f, false);
}

namespace
{
	// Route in metres (X north, Y east, altitude above the lake surface): castle, lake skim, forest, Hogsmeade, station.
	struct FWaypoint { double X, Y, Alt; };
	const FWaypoint GRoute[] = {
		{0, 0, 140}, {500, -500, 12}, {0, -900, 10}, {800, 1200, 90}, {1560, -2235, 120}, {-450, -1365, 80},
	};
}

void AHPFlightGameMode::HandleImpact(float Severity, const FHitResult& Hit)
{
	++ImpactCount;
	UE_LOG(LogTemp, Display, TEXT("HPFLY impact #%d severity %.2f with %s"), ImpactCount, Severity, *GetNameSafe(Hit.GetActor()));
}

void AHPFlightGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bAutoFly)
	{
		return;
	}
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ABroomPawn* Pawn = PC ? Cast<ABroomPawn>(PC->GetPawn()) : nullptr;
	UBroomMovementComponent* Move = Pawn ? Pawn->FindComponentByClass<UBroomMovementComponent>() : nullptr;
	if (!Move)
	{
		return;
	}
	if (!bImpactBound)
	{
		Move->OnBroomImpact.AddDynamic(this, &AHPFlightGameMode::HandleImpact);
		bImpactBound = true;
	}

	AutoFlyTime += DeltaSeconds;
	const FVector Loc = Pawn->GetActorLocation() / 100.0;
	const FWaypoint& Target = GRoute[WaypointIndex];
	const double Dx = Target.X - Loc.X, Dy = Target.Y - Loc.Y;
	const double Dist = FMath::Sqrt(Dx * Dx + Dy * Dy);
	if (Dist < 80.0)
	{
		UE_LOG(LogTemp, Display, TEXT("HPFLY reached waypoint %d at t=%.0fs"), WaypointIndex, AutoFlyTime);
		WaypointIndex = (WaypointIndex + 1) % UE_ARRAY_COUNT(GRoute);
	}

	const double WantYaw = FMath::RadiansToDegrees(FMath::Atan2(Dy, Dx));
	const double YawError = FMath::FindDeltaAngleDegrees(Pawn->GetActorRotation().Yaw, WantYaw);
	const float Turn = FMath::Clamp(static_cast<float>(YawError / 35.0), -1.f, 1.f);
	const float Pitch = FMath::Clamp(static_cast<float>((Target.Alt - Loc.Z) / 60.0), -1.f, 1.f);
	Move->SetFlightInput(Pitch, Turn, 1.f, 0.f, false);

	if (AutoFlyTime >= NextLogTime)
	{
		NextLogTime += 3.f;
		UE_LOG(LogTemp, Display, TEXT("HPFLY t=%.0f wp=%d pos=(%.0f,%.0f,%.0f) dist=%.0f yawErr=%.0f speed=%.1f hover=%d skim=%d water=%d outside=%d impacts=%d"),
			AutoFlyTime, WaypointIndex, Loc.X, Loc.Y, Loc.Z, Dist, YawError, Move->GetAirspeed(), Move->IsHovering(), Move->IsSkimming(),
			Move->IsSkimmingWater(), Move->IsOutsideBoundary(), ImpactCount);
	}
	if (AutoFlyTime > 200.f)
	{
		UE_LOG(LogTemp, Display, TEXT("HPFLY done: %d impacts"), ImpactCount);
		PC->ConsoleCommand(TEXT("quit"));
	}
}
