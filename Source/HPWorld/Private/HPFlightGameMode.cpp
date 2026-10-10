#include "HPFlightGameMode.h"

#include "BroomPawn.h"
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
	};
}

AHPFlightGameMode::AHPFlightGameMode()
{
	DefaultPawnClass = ABroomPawn::StaticClass();
}

void AHPFlightGameMode::BeginPlay()
{
	Super::BeginPlay();
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
