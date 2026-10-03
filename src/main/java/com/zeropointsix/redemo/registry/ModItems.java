package com.zeropointsix.redemo.registry;

import com.zeropointsix.redemo.ResidentEvilMod;
import net.minecraft.world.item.Item;
import net.minecraftforge.common.ForgeSpawnEggItem;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class ModItems {
    public static final DeferredRegister<Item> ITEMS = DeferredRegister.create(ForgeRegistries.ITEMS, ResidentEvilMod.MOD_ID);
    public static final RegistryObject<Item> LICKER_EGG = ITEMS.register("licker_spawn_egg", () -> new ForgeSpawnEggItem(ModEntities.LICKER, 0x9F393D, 0xF8C4BF, new Item.Properties()));
    public static final RegistryObject<Item> TYRANT_EGG = ITEMS.register("tyrant_spawn_egg", () -> new ForgeSpawnEggItem(ModEntities.TYRANT, 0x232B30, 0xA6A392, new Item.Properties()));
    public static final RegistryObject<Item> G1_BIRKIN_EGG = ITEMS.register("g1_birkin_spawn_egg", () -> new ForgeSpawnEggItem(ModEntities.G1_BIRKIN, 0x71373D, 0xF3BB3D, new Item.Properties()));

    private ModItems() { }
}
