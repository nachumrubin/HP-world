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
};
