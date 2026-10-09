#include "HPLandscapeTools.h"

#if WITH_EDITOR
#include "Editor.h"
#include "Landscape.h"
#include "LandscapeInfo.h"
#include "LandscapeProxy.h"
#include "Misc/FileHelper.h"
#endif

bool UHPLandscapeTools::ImportLandscapeFromR16(const FString& HeightmapPath, int32 Size, FVector Location, FVector Scale, const FString& Label)
{
#if WITH_EDITOR
	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	TArray<uint8> Bytes;
	if (!World || !FFileHelper::LoadFileToArray(Bytes, *HeightmapPath) || Bytes.Num() != Size * Size * 2)
	{
		UE_LOG(LogTemp, Error, TEXT("HPLandscape: no world or bad heightmap '%s' (%d bytes)"), *HeightmapPath, Bytes.Num());
		return false;
	}

	TArray<uint16> Heights;
	Heights.SetNumUninitialized(Size * Size);
	FMemory::Memcpy(Heights.GetData(), Bytes.GetData(), Bytes.Num());

	const int32 QuadsPerSection = 63;
	const int32 SectionsPerComponent = 1;

	ALandscape* Landscape = World->SpawnActor<ALandscape>(Location, FRotator::ZeroRotator);
	Landscape->SetActorRelativeScale3D(Scale);
	Landscape->StaticLightingLOD = 2;

	TMap<FGuid, TArray<uint16>> HeightData;
	HeightData.Add(FGuid(), MoveTemp(Heights));
	TMap<FGuid, TArray<FLandscapeImportLayerInfo>> LayerData;
	LayerData.Add(FGuid(), TArray<FLandscapeImportLayerInfo>());

	Landscape->Import(FGuid::NewGuid(), 0, 0, Size - 1, Size - 1, SectionsPerComponent, QuadsPerSection, HeightData, *HeightmapPath,
		LayerData, ELandscapeImportAlphamapType::Additive, TArrayView<const FLandscapeLayer>());

	if (ULandscapeInfo* Info = Landscape->GetLandscapeInfo())
	{
		Info->UpdateLayerInfoMap(Landscape);
	}
	Landscape->SetActorLabel(Label);
	return true;
#else
	return false;
#endif
}
