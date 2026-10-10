#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "HPFlightGameMode.generated.h"

// M0 game mode: spawns the player on a broom at the PlayerStart and nothing else.
UCLASS()
class HPWORLD_API AHPFlightGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AHPFlightGameMode();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** `-HPAutoFly`: steer the broom through a fixed route, log telemetry and impacts, then quit. A scripted flight test, not gameplay. */
	UFUNCTION()
	void HandleImpact(float Severity, const FHitResult& Hit);

	bool bAutoFly = false;
	float AutoFlyTime = 0.f;
	float NextLogTime = 0.f;
	int32 WaypointIndex = 0;
	int32 ImpactCount = 0;
	bool bImpactBound = false;

	/** `-HPShots` on the command line: fly a fixed camera through the readability viewpoints, save screenshots and quit. */
	void StartScreenshotRun();
	void NextScreenshot();

	FTimerHandle ShotTimer;
	TWeakObjectPtr<class ACameraActor> ShotCamera;
	int32 ShotIndex = 0;
	bool bShotPending = false;
};
