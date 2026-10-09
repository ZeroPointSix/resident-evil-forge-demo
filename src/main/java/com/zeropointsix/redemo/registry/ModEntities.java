package com.zeropointsix.redemo.registry;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.entity.G1BirkinEntity;
import com.zeropointsix.redemo.entity.LickerEntity;
import com.zeropointsix.redemo.entity.TyrantEntity;
import com.zeropointsix.redemo.entity.TyrantDebrisEntity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraftforge.event.entity.EntityAttributeCreationEvent;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class ModEntities {
    public static final DeferredRegister<EntityType<?>> TYPES = DeferredRegister.create(ForgeRegistries.ENTITY_TYPES, ResidentEvilMod.MOD_ID);
    public static final RegistryObject<EntityType<LickerEntity>> LICKER = TYPES.register("licker", () -> EntityType.Builder.of(LickerEntity::new, MobCategory.MONSTER)
            .sized(1.35F, 1.05F).clientTrackingRange(12).build("re_demo:licker"));
    public static final RegistryObject<EntityType<TyrantEntity>> TYRANT = TYPES.register("tyrant", () -> EntityType.Builder.of(TyrantEntity::new, MobCategory.MONSTER)
            .sized(1.3F, 4.0F).clientTrackingRange(16).build("re_demo:tyrant"));
    public static final RegistryObject<EntityType<TyrantDebrisEntity>> TYRANT_DEBRIS = TYPES.register("tyrant_debris", () -> EntityType.Builder.<TyrantDebrisEntity>of(TyrantDebrisEntity::new, MobCategory.MISC)
            .sized(0.45F, 0.45F).clientTrackingRange(8).updateInterval(1).build("re_demo:tyrant_debris"));
    public static final RegistryObject<EntityType<G1BirkinEntity>> G1_BIRKIN = TYPES.register("g1_birkin", () -> EntityType.Builder.of(G1BirkinEntity::new, MobCategory.MONSTER)
            .sized(1.5F, 2.9F).clientTrackingRange(16).build("re_demo:g1_birkin"));

    public static void registerAttributes(EntityAttributeCreationEvent event) {
        event.put(LICKER.get(), LickerEntity.attributes().build());
        event.put(TYRANT.get(), TyrantEntity.attributes().build());
        event.put(G1_BIRKIN.get(), G1BirkinEntity.attributes().build());
    }

    private ModEntities() { }
}
