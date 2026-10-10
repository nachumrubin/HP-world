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

private:
	/** `-HPShots` on the command line: fly a fixed camera through the readability viewpoints, save screenshots and quit. */
	void StartScreenshotRun();
	void NextScreenshot();

	FTimerHandle ShotTimer;
	TWeakObjectPtr<class ACameraActor> ShotCamera;
	int32 ShotIndex = 0;
	bool bShotPending = false;
};
