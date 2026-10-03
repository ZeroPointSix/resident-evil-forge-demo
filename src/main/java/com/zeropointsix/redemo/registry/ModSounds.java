package com.zeropointsix.redemo.registry;

import com.zeropointsix.redemo.ResidentEvilMod;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class ModSounds {
    public static final DeferredRegister<SoundEvent> SOUNDS = DeferredRegister.create(ForgeRegistries.SOUND_EVENTS, ResidentEvilMod.MOD_ID);
    public static final RegistryObject<SoundEvent> LICKER_HISS = sound("licker_hiss");
    public static final RegistryObject<SoundEvent> HEAVY_STEP = sound("heavy_step");
    public static final RegistryObject<SoundEvent> IMPACT = sound("impact");
    public static final RegistryObject<SoundEvent> RAGE = sound("rage");
    public static final RegistryObject<SoundEvent> EYE_OPEN = sound("eye_open");

    private static RegistryObject<SoundEvent> sound(String name) {
        return SOUNDS.register(name, () -> SoundEvent.createVariableRangeEvent(new ResourceLocation(ResidentEvilMod.MOD_ID, name)));
    }

    private ModSounds() { }
}
