"""Config- und Options-Flow für Drohnenspot."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_EXCLUDE_FOREST,
    CONF_MAX_ROAD_DISTANCE_M,
    CONF_MIN_ELEVATION,
    CONF_POI_BONUS,
    CONF_POI_BONUS_RADIUS_M,
    CONF_POI_CATEGORIES,
    CONF_RADIUS_KM,
    CONF_REQUIRE_ROAD_ACCESS,
    CONF_SPOT_COUNT,
    DEFAULT_EXCLUDE_FOREST,
    DEFAULT_MAX_ROAD_DISTANCE_M,
    DEFAULT_MIN_ELEVATION,
    DEFAULT_POI_BONUS,
    DEFAULT_POI_BONUS_RADIUS_M,
    DEFAULT_POI_CATEGORIES,
    DEFAULT_RADIUS_KM,
    DEFAULT_REQUIRE_ROAD_ACCESS,
    DEFAULT_SPOT_COUNT,
    DOMAIN,
    POI_CATEGORY_OPTIONS,
)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_RADIUS_KM, default=defaults.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)
            ): vol.All(vol.Coerce(float), vol.Range(min=1, max=50)),
            vol.Required(
                CONF_SPOT_COUNT,
                default=defaults.get(CONF_SPOT_COUNT, DEFAULT_SPOT_COUNT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Required(
                CONF_MIN_ELEVATION,
                default=defaults.get(CONF_MIN_ELEVATION, DEFAULT_MIN_ELEVATION),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=3000)),
            vol.Required(
                CONF_EXCLUDE_FOREST,
                default=defaults.get(CONF_EXCLUDE_FOREST, DEFAULT_EXCLUDE_FOREST),
            ): bool,
            vol.Required(
                CONF_REQUIRE_ROAD_ACCESS,
                default=defaults.get(
                    CONF_REQUIRE_ROAD_ACCESS, DEFAULT_REQUIRE_ROAD_ACCESS
                ),
            ): bool,
            vol.Required(
                CONF_MAX_ROAD_DISTANCE_M,
                default=defaults.get(
                    CONF_MAX_ROAD_DISTANCE_M, DEFAULT_MAX_ROAD_DISTANCE_M
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=5000)),
            vol.Required(
                CONF_POI_BONUS,
                default=defaults.get(CONF_POI_BONUS, DEFAULT_POI_BONUS),
            ): bool,
            vol.Required(
                CONF_POI_BONUS_RADIUS_M,
                default=defaults.get(
                    CONF_POI_BONUS_RADIUS_M, DEFAULT_POI_BONUS_RADIUS_M
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=50, max=10000)),
            vol.Required(
                CONF_POI_CATEGORIES,
                default=defaults.get(CONF_POI_CATEGORIES, DEFAULT_POI_CATEGORIES),
            ): cv.multi_select(POI_CATEGORY_OPTIONS),
        }
    )


class DrohnenspotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung über die Oberfläche (eine Instanz)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Drohnenspot", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Required(CONF_RADIUS_KM, default=DEFAULT_RADIUS_KM): vol.All(
                    vol.Coerce(float), vol.Range(min=1, max=50)
                ),
                vol.Required(CONF_SPOT_COUNT, default=DEFAULT_SPOT_COUNT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=30)
                ),
                vol.Required(
                    CONF_MIN_ELEVATION, default=DEFAULT_MIN_ELEVATION
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=3000)),
                vol.Required(
                    CONF_EXCLUDE_FOREST, default=DEFAULT_EXCLUDE_FOREST
                ): bool,
                vol.Required(
                    CONF_REQUIRE_ROAD_ACCESS, default=DEFAULT_REQUIRE_ROAD_ACCESS
                ): bool,
                vol.Required(
                    CONF_MAX_ROAD_DISTANCE_M, default=DEFAULT_MAX_ROAD_DISTANCE_M
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=5000)),
                vol.Required(
                    CONF_POI_BONUS, default=DEFAULT_POI_BONUS
                ): bool,
                vol.Required(
                    CONF_POI_BONUS_RADIUS_M, default=DEFAULT_POI_BONUS_RADIUS_M
                ): vol.All(vol.Coerce(int), vol.Range(min=50, max=10000)),
                vol.Required(
                    CONF_POI_CATEGORIES, default=DEFAULT_POI_CATEGORIES
                ): cv.multi_select(POI_CATEGORY_OPTIONS),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DrohnenspotOptionsFlow()


class DrohnenspotOptionsFlow(OptionsFlow):
    """Radius / Anzahl / Mindesthöhe nachträglich ändern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        merged = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(merged)
        )
