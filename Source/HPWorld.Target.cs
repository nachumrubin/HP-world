using UnrealBuildTool;

public class HPWorldTarget : TargetRules
{
	public HPWorldTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "HPWorld", "HPFlight" });
	}
}
