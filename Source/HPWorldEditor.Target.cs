using UnrealBuildTool;

public class HPWorldEditorTarget : TargetRules
{
	public HPWorldEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "HPWorld", "HPFlight" });
	}
}
