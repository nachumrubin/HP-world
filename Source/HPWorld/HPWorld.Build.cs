using UnrealBuildTool;

public class HPWorld : ModuleRules
{
	public HPWorld(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "HPFlight" });
	}
}
