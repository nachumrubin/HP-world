#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "HPLandscapeTools.generated.h"

/** Editor-only helpers for the M1 landscape, called from Tools/Unreal/import_landscape_m1.py. */
UCLASS()
class HPWORLD_API UHPLandscapeTools : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Spawns a Landscape in the editor world from a raw 16-bit little-endian heightmap (Size x Size vertices). */
	UFUNCTION(BlueprintCallable, Category = "HP|Landscape")
	static bool ImportLandscapeFromR16(const FString& HeightmapPath, int32 Size, FVector Location, FVector Scale, const FString& Label);
};
