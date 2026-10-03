package com.zeropointsix.redemo.client;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.entity.EncounterMob;
import com.zeropointsix.redemo.registry.ModEntities;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.EntityRenderersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

@Mod.EventBusSubscriber(modid = ResidentEvilMod.MOD_ID, bus = Mod.EventBusSubscriber.Bus.MOD, value = Dist.CLIENT)
public final class ClientRegistration {
    private ClientRegistration() { }

    @SubscribeEvent
    public static void register(EntityRenderersEvent.RegisterRenderers event) {
        event.registerEntityRenderer(ModEntities.LICKER.get(), context -> new CreatureRenderer<>(context, "licker", 0.75F));
        event.registerEntityRenderer(ModEntities.TYRANT.get(), context -> new CreatureRenderer<>(context, "tyrant", 0.8F));
        event.registerEntityRenderer(ModEntities.G1_BIRKIN.get(), context -> new CreatureRenderer<>(context, "g1_birkin", 0.95F));
    }

    private static final class CreatureRenderer<T extends EncounterMob> extends GeoEntityRenderer<T> {
        CreatureRenderer(EntityRendererProvider.Context context, String id, float shadow) {
            super(context, new CreatureModel<>(id));
            shadowRadius = shadow;
        }
    }
}
