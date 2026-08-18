"""Full 12-month data pull for HK_Search_Leads."""
import asyncio, json
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
SP="/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/"
CID="22972642686"; D="segments.date BETWEEN '2025-08-18' AND '2026-08-17'"
Q={
"settings":("SELECT campaign.id, campaign.name, campaign.status, campaign.start_date, "
 "campaign.bidding_strategy_type, campaign.maximize_conversions.target_cpa_micros, "
 "campaign.network_settings.target_google_search, campaign.network_settings.target_search_network, "
 "campaign.network_settings.target_content_network, campaign.network_settings.target_partner_search_network, "
 "campaign.geo_target_type_setting.positive_geo_target_type, "
 "campaign.geo_target_type_setting.negative_geo_target_type, "
 "campaign_budget.amount_micros, campaign_budget.explicitly_shared, "
 "campaign.optimization_score, campaign.ad_serving_optimization_status "
 f"FROM campaign WHERE campaign.id={CID}"),
"monthly":("SELECT segments.month, metrics.impressions, metrics.clicks, metrics.cost_micros, "
 "metrics.conversions, metrics.all_conversions, metrics.ctr, metrics.average_cpc, "
 "metrics.search_impression_share, metrics.search_budget_lost_impression_share, "
 "metrics.search_rank_lost_impression_share "
 f"FROM campaign WHERE campaign.id={CID} AND {D}"),
"keywords":("SELECT ad_group.name, ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
 "ad_group_criterion.keyword.match_type, ad_group_criterion.status, "
 "ad_group_criterion.quality_info.quality_score, "
 "ad_group_criterion.quality_info.creative_quality_score, "
 "ad_group_criterion.quality_info.post_click_quality_score, "
 "ad_group_criterion.quality_info.search_predicted_ctr, "
 "ad_group_criterion.effective_cpc_bid_micros, metrics.impressions, metrics.clicks, "
 "metrics.cost_micros, metrics.conversions, metrics.all_conversions, metrics.ctr, "
 "metrics.average_cpc, metrics.search_impression_share "
 f"FROM keyword_view WHERE campaign.id={CID} AND {D}"),
"kw_all":("SELECT ad_group.name, ad_group.status, ad_group_criterion.criterion_id, "
 "ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, "
 "ad_group_criterion.status, ad_group_criterion.negative "
 f"FROM ad_group_criterion WHERE campaign.id={CID} AND ad_group_criterion.type='KEYWORD'"),
"terms":("SELECT search_term_view.search_term, search_term_view.status, ad_group.name, "
 "segments.keyword.info.text, segments.keyword.info.match_type, "
 "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, "
 "metrics.all_conversions, metrics.ctr "
 f"FROM search_term_view WHERE campaign.id={CID} AND {D}"),
"negatives":("SELECT campaign_criterion.criterion_id, campaign_criterion.keyword.text, "
 "campaign_criterion.keyword.match_type, campaign_criterion.type, campaign_criterion.negative "
 f"FROM campaign_criterion WHERE campaign.id={CID} AND campaign_criterion.negative=TRUE"),
"shared":("SELECT shared_set.id, shared_set.name, shared_set.type, shared_set.status "
 f"FROM campaign_shared_set WHERE campaign.id={CID}"),
"geo":("SELECT campaign_criterion.criterion_id, campaign_criterion.location.geo_target_constant, "
 "campaign_criterion.type, campaign_criterion.negative, campaign_criterion.language.language_constant, "
 "campaign_criterion.proximity.radius, campaign_criterion.ad_schedule.day_of_week "
 f"FROM campaign_criterion WHERE campaign.id={CID} AND campaign_criterion.negative=FALSE"),
"ads":("SELECT ad_group.name, ad_group_ad.ad.id, ad_group_ad.status, metrics.impressions, "
 "metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.ctr "
 f"FROM ad_group_ad WHERE campaign.id={CID} AND {D}"),
"conv":("SELECT segments.conversion_action_name, segments.conversion_action_category, "
 "metrics.all_conversions, metrics.conversions "
 f"FROM campaign WHERE campaign.id={CID} AND {D}"),
"device":("SELECT segments.device, metrics.impressions, metrics.clicks, metrics.cost_micros, "
 f"metrics.conversions, metrics.ctr FROM campaign WHERE campaign.id={CID} AND {D}"),
"user_loc":("SELECT user_location_view.country_criterion_id, user_location_view.targeting_location, "
 "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions "
 f"FROM user_location_view WHERE campaign.id={CID} AND {D}"),
"dow":("SELECT segments.day_of_week, metrics.impressions, metrics.clicks, metrics.cost_micros, "
 f"metrics.conversions FROM campaign WHERE campaign.id={CID} AND {D}"),
"ad_groups":("SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.type, "
 "ad_group.cpc_bid_micros, metrics.impressions, metrics.clicks, metrics.cost_micros, "
 f"metrics.conversions FROM ad_group WHERE campaign.id={CID} AND {D}"),
}
async def main():
    c=GoogleAdsClient(load_config()); out={}
    for k,q in Q.items():
        try:
            out[k]=await c.search(q); print(f"{k:10} {len(out[k])}")
        except Exception as e:
            out[k]={"error":str(e)[:300]}; print(f"{k:10} ERROR {str(e)[:150]}")
    json.dump(out, open(SP+"hk_audit.json","w"), indent=1, default=str)
asyncio.run(main())
