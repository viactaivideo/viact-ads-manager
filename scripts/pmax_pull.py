# -*- coding: utf-8 -*-
"""Lifetime pull for HK_Pmax_4S."""
import asyncio, json
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
SP="/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/"
C="23029018962"; D="segments.date BETWEEN '2024-01-01' AND '2026-08-18'"
Q={
"settings":("SELECT campaign.id, campaign.name, campaign.status, campaign.start_date_time, "
 "campaign.bidding_strategy_type, campaign.advertising_channel_type, "
 "campaign.optimization_score, "
 "campaign.network_settings.target_google_search, campaign.network_settings.target_search_network, "
 "campaign.network_settings.target_content_network, campaign.network_settings.target_partner_search_network, "
 "campaign.geo_target_type_setting.positive_geo_target_type, "
 "campaign.geo_target_type_setting.negative_geo_target_type, campaign_budget.amount_micros, "
 "campaign.maximize_conversions.target_cpa_micros, campaign.serving_status, "
 "campaign.final_url_suffix, campaign.tracking_url_template "
 f"FROM campaign WHERE campaign.id={C}"),
"monthly":("SELECT segments.month, metrics.impressions, metrics.clicks, metrics.cost_micros, "
 "metrics.conversions, metrics.all_conversions, metrics.ctr, metrics.average_cpc, "
 "metrics.conversions_value, metrics.interactions "
 f"FROM campaign WHERE campaign.id={C} AND {D}"),
"conv_action":("SELECT segments.conversion_action_name, segments.conversion_action_category, "
 f"metrics.all_conversions, metrics.conversions FROM campaign WHERE campaign.id={C} AND {D}"),
"asset_groups":("SELECT asset_group.id, asset_group.name, asset_group.status, "
 "asset_group.final_urls, asset_group.path1, asset_group.path2, asset_group.primary_status, "
 "asset_group.primary_status_reasons, asset_group.ad_strength "
 f"FROM asset_group WHERE campaign.id={C}"),
"ag_perf":("SELECT asset_group.id, asset_group.name, metrics.impressions, metrics.clicks, "
 "metrics.cost_micros, metrics.conversions, metrics.all_conversions "
 f"FROM asset_group WHERE campaign.id={C} AND {D}"),
"signals":("SELECT asset_group.id, asset_group.name, asset_group_signal.audience.audience, "
 "asset_group_signal.search_theme.text, asset_group_signal.resource_name "
 f"FROM asset_group_signal WHERE campaign.id={C}"),
"criteria":("SELECT campaign_criterion.criterion_id, campaign_criterion.type, "
 "campaign_criterion.negative, campaign_criterion.location.geo_target_constant, "
 "campaign_criterion.language.language_constant, campaign_criterion.keyword.text, "
 "campaign_criterion.keyword.match_type, campaign_criterion.brand_list.shared_set, "
 "campaign_criterion.webpage.conditions, campaign_criterion.status "
 f"FROM campaign_criterion WHERE campaign.id={C}"),
"search_terms":("SELECT campaign_search_term_insight.category_label, "
 "campaign_search_term_insight.id, metrics.impressions, metrics.clicks, "
 "metrics.conversions, metrics.conversions_from_interactions_rate "
 f"FROM campaign_search_term_insight WHERE segments.date BETWEEN '2025-08-18' AND '2026-08-18' "
 f"AND campaign_search_term_insight.campaign_id={C}"),
"url_exp":("SELECT campaign.id, campaign.name, campaign.performance_max_upgrade.pre_upgrade_campaign, "
 f"campaign.url_expansion_opt_out FROM campaign WHERE campaign.id={C}"),
"listing":("SELECT asset_group_listing_group_filter.id, asset_group.name, "
 "asset_group_listing_group_filter.type, asset_group_listing_group_filter.case_value.product_type.value "
 f"FROM asset_group_listing_group_filter WHERE campaign.id={C}"),
"device":("SELECT segments.device, metrics.impressions, metrics.clicks, metrics.cost_micros, "
 f"metrics.conversions, metrics.all_conversions FROM campaign WHERE campaign.id={C} AND {D}"),
"network":("SELECT segments.ad_network_type, metrics.impressions, metrics.clicks, "
 "metrics.cost_micros, metrics.conversions, metrics.all_conversions "
 f"FROM campaign WHERE campaign.id={C} AND {D}"),
"conv_lag":("SELECT segments.date, metrics.conversions, metrics.all_conversions, "
 f"metrics.cost_micros, metrics.clicks FROM campaign WHERE campaign.id={C} AND {D}"),
}
async def m():
    c=GoogleAdsClient(load_config()); out={}
    for k,q in Q.items():
        try:
            out[k]=await c.search(q); print(f"{k:14} {len(out[k])}")
        except Exception as e:
            out[k]={"error":str(e)[:250]}; print(f"{k:14} ERROR {str(e)[:170]}")
    json.dump(out,open(SP+"pmax_hk.json","w"),indent=1,default=str)
asyncio.run(m())
