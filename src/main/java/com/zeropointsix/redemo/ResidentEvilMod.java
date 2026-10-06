package com.zeropointsix.redemo;

import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.registry.ModEntities;
import com.zeropointsix.redemo.registry.ModItems;
import com.zeropointsix.redemo.registry.ModSounds;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraftforge.event.BuildCreativeModeTabContentsEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.config.ModConfig;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.fml.ModLoadingContext;
import software.bernie.geckolib.GeckoLib;

@Mod(ResidentEvilMod.MOD_ID)
public final class ResidentEvilMod {
    public static final String MOD_ID = "re_demo";

    public ResidentEvilMod() {
        IEventBus bus = FMLJavaModLoadingContext.get().getModEventBus();
        GeckoLib.initialize();
        ModEntities.TYPES.register(bus);
        ModItems.ITEMS.register(bus);
        ModSounds.SOUNDS.register(bus);
        bus.addListener(ModEntities::registerAttributes);
        bus.addListener(this::creativeItems);
        ModLoadingContext.get().registerConfig(ModConfig.Type.COMMON, CommonConfig.SPEC);
    }

    private void creativeItems(BuildCreativeModeTabContentsEvent event) {
        if (event.getTabKey() == CreativeModeTabs.SPAWN_EGGS) {
            ModItems.ITEMS.getEntries().forEach(event::accept);
        }
    }
}
