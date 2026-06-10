/**
 * Action Cards for Miniapps - Renders structured data from voice agent.

 */

class ActionCards {
  constructor(container) {
    this.container = container;
    this.cards = [];
  }

  /**
   * Add a new action card
   * @param {Object} cardData - Card data object with type and content
   */
  addCard(cardData) {
    if (!cardData || !cardData.type) return;
    
    const card = {
      ...cardData,
      _key: `${cardData.type}-${Date.now()}`
    };
    
    this.cards.push(card);
    this.render();
  }

  /**
   * Clear all cards
   */
  clear() {
    this.cards = [];
    this.render();
  }

  /**
   * Render all cards
   */
  render() {
    if (!this.container) return;

    this.container.innerHTML = '';
    
    if (this.cards.length === 0) return;

    const cardsContainer = document.createElement('div');
    cardsContainer.className = 'action-cards-container space-y-3';

    this.cards.forEach(card => {
      const cardElement = this.createCardElement(card);
      if (cardElement) {
        cardsContainer.appendChild(cardElement);
      }
    });

    this.container.appendChild(cardsContainer);
  }

  /**
   * Create card element based on type
   * @param {Object} card - Card data
   * @returns {HTMLElement|null} Card element
   */
  createCardElement(card) {
    switch (card.type) {
      // Batch cards
      case 'batch_detail':
        return this.createBatchDetailCard(card);
      case 'batch_list':
        return this.createBatchListCard(card);

      // Supply-chain events
      case 'record_commission':
        return this.createEventConfirmCard(card, 'Commissioned', '#10B981');
      case 'record_shipment':
        return this.createEventConfirmCard(card, 'Shipped', '#6366F1');
      case 'record_receipt':
        return this.createEventConfirmCard(card, 'Received', '#06B6D4');
      case 'record_transformation':
        return this.createTransformationCard(card);
      case 'pack_batches':
        return this.createPackCard(card, 'Packed');
      case 'unpack_batches':
        return this.createPackCard(card, 'Unpacked');
      case 'split_batch':
        return this.createSplitCard(card);

      // Knowledge
      case 'search_knowledge':
        return this.createKnowledgeCard(card);

      // Marketplace
      case 'create_rfq':
        return this.createRfqCreatedCard(card);
      case 'browse_rfqs':
        return this.createRfqListCard(card);
      case 'submit_offer':
        return this.createOfferCard(card, 'Submitted');
      case 'accept_offer':
        return this.createOfferCard(card, 'Accepted', '#10B981');
      case 'list_my_offers':
        return this.createOfferListCard(card);
      case 'list_rfq_offers':
        return this.createRfqOffersCard(card);

      // Containers & pools
      case 'browse_containers':
        return this.createContainerListCard(card);
      case 'purchase_container':
        return this.createPurchaseCard(card);
      case 'browse_pools':
        return this.createPoolListCard(card);
      case 'commit_to_pool':
        return this.createPoolCommitCard(card);
      case 'list_my_commitments':
        return this.createCommitmentListCard(card);

      // Compliance
      case 'check_eudr_compliance':
        return this.createEudrComplianceCard(card);
      case 'check_mass_balance':
        return this.createMassBalanceCard(card);

      // Settlement / Payment
      case 'confirm_payment':
      case 'check_payment_status':
      case 'record_cooperative_payout':
      case 'confirm_payment_received':
        return this.createPaymentCard(card);
      case 'dispute_payment':
        return this.createDisputePaymentCard(card);
      case 'confirm_shipment':
        return this.createShipmentConfirmCard(card);
      case 'confirm_delivery':
        return this.createDeliveryConfirmCard(card);

      // DPP / Traceability
      case 'dpp_passport':
        return this.createDppPassportCard(card);
      case 'get_container_dpp':
        return this.createContainerDppCard(card);
      case 'trace_lineage':
        return this.createLineageCard(card);
      case 'validate_dpp':
        return this.createValidateDppCard(card);

      default:
        return this.createGenericCard(card);
    }
  }

  /**
   * Create base card structure
   * @param {string} title - Card title
   * @param {string} accent - Accent color
   * @returns {HTMLElement} Card element
   */
  createBaseCard(title, accent = '#10B981') {
    const card = document.createElement('div');
    card.className = 'action-card';
    card.style.cssText = `
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 12px;
      padding: 16px;
      backdrop-filter: blur(8px);
      margin-bottom: 12px;
    `;

    const header = document.createElement('div');
    header.className = 'card-header';
    header.style.cssText = `
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
    `;

    const icon = document.createElement('div');
    icon.style.cssText = `
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: ${accent};
    `;

    const titleEl = document.createElement('h3');
    titleEl.textContent = title;
    titleEl.style.cssText = `
      font-size: 14px;
      font-weight: 600;
      color: white;
      margin: 0;
    `;

    header.appendChild(icon);
    header.appendChild(titleEl);
    card.appendChild(header);

    return card;
  }

  /**
   * Create batch detail card
   */
  createBatchDetailCard(card) {
    const baseCard = this.createBaseCard('Batch Details');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    // Match web-frontend: const b = data.batch || data
    const b = card.data?.batch || card.data || card;
    
    content.innerHTML = `
      <div style="margin-bottom: 8px;"><strong>Batch ID:</strong> ${b.batch_id || b.id || 'N/A'}</div>
      <div style="margin-bottom: 8px;"><strong>Origin:</strong> ${b.origin || 'N/A'}</div>
      <div style="margin-bottom: 8px;"><strong>Variety:</strong> ${b.variety || 'N/A'}</div>
      <div style="margin-bottom: 8px;"><strong>Grade:</strong> ${b.quality_grade || b.grade || 'N/A'}</div>
      <div style="margin-bottom: 8px;"><strong>Weight:</strong> ${b.quantity_kg ? `${b.quantity_kg} kg` : (b.weight_kg ? `${b.weight_kg} kg` : (b.weight ? `${b.weight} kg` : 'N/A'))}</div>
      ${b.altitude ? `<div style="margin-bottom: 8px;"><strong>Altitude:</strong> ${b.altitude} m</div>` : ''}
      <div style="margin-bottom: 8px;"><strong>Processing:</strong> ${b.processing_method || 'N/A'}</div>
      <div style="margin-bottom: 8px;"><strong>Status:</strong> ${b.status || 'N/A'}</div>
      ${b.farmer_name ? `<div style="margin-bottom: 8px;"><strong>Farmer:</strong> ${b.farmer_name}</div>` : ''}
      ${b.cooperative ? `<div style="margin-bottom: 8px;"><strong>Cooperative:</strong> ${b.cooperative}</div>` : ''}
      ${b.harvest_date ? `<div><strong>Harvested:</strong> ${b.harvest_date}</div>` : ''}
    `;
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create batch list card
   */
  createBatchListCard(card) {
    const batches = card.data?.batches || [];
    const baseCard = this.createBaseCard(`Batches (${card.data?.count || batches.length})`);
    const content = document.createElement('div');
    
    // Mobile-responsive: horizontal scroll on small screens, normal layout on big screens
    const isMobile = window.innerWidth < 640;
    content.style.cssText = isMobile 
      ? 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-x: auto; overflow-y: hidden; width: 100%;'
      : 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto;';
    
    // Helper function to get status color
    const getStatusColor = (status) => {
      const colors = {
        'COMMISSIONED': '#10b981',
        'HARVESTED': '#10b981', 
        'PROCESSED': '#3b82f6',
        'EXPORTED': '#8b5cf6',
        'DELIVERED': '#06b6d4',
        'ROASTED': '#f59e0b'
      };
      return colors[status?.toUpperCase()] || '#6b7280';
    };
    
    if (card.data && Array.isArray(card.data.batches)) {
      const allBatches = card.data.batches;
      const visibleBatches = allBatches.slice(0, 4); // Match web-frontend limit
      
      // Create batch list content
      const batchListContent = document.createElement('div');
      batchListContent.className = 'batch-list-content';
      batchListContent.innerHTML = visibleBatches.map(batch => {
        // Mobile-responsive styling
        const isMobile = window.innerWidth < 640;
        const itemStyle = isMobile 
          ? 'display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 200px; flex-shrink: 0;'
          : 'display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;';
        
        return `
        <div style="${itemStyle}">
          <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
            <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.7); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${batch.batch_id || batch.id}</div>
            <div style="font-size: 10px; color: rgba(255, 255, 255, 0.3); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${batch.origin || 'Unknown'}${batch.variety ? ` • ${batch.variety}` : ''}</div>
          </div>
          <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${getStatusColor(batch.status)}20; color: ${getStatusColor(batch.status)}; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${batch.status || 'UNKNOWN'}</div>
        </div>
      `;
      }).join('');
      
      content.appendChild(batchListContent);
      
      // Add show all/less button if there are more batches
      if (allBatches.length > 4) {
        const showButton = document.createElement('button');
        showButton.style.cssText = 'width: 100%; margin-top: 8px; font-size: 10px; color: rgba(99, 102, 241, 0.6); cursor: pointer; background: none; border: none; padding: 4px;';
        showButton.textContent = `Show all ${allBatches.length} batches...`;
        
        let isExpanded = false;
        showButton.addEventListener('click', () => {
          if (!isExpanded) {
            // Show all batches
            batchListContent.innerHTML = allBatches.map(batch => {
                // Mobile-responsive styling
                const isMobile = window.innerWidth < 640;
                const itemStyle = isMobile 
                  ? 'display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 200px; flex-shrink: 0;'
                  : 'display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;';
                
                return `
              <div style="${itemStyle}">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.7); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${batch.batch_id || batch.id}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.3); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${batch.origin || 'Unknown'}${batch.variety ? ` • ${batch.variety}` : ''}</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${getStatusColor(batch.status)}20; color: ${getStatusColor(batch.status)}; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${batch.status || 'UNKNOWN'}</div>
              </div>
            `;
              }).join('');
            showButton.textContent = 'Show less';
            isExpanded = true;
          } else {
            // Show only first 4 batches
            batchListContent.innerHTML = visibleBatches.map(batch => {
                // Mobile-responsive styling
                const isMobile = window.innerWidth < 640;
                const itemStyle = isMobile 
                  ? 'display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 200px; flex-shrink: 0;'
                  : 'display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;';
                
                return `
              <div style="${itemStyle}">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.7); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${batch.batch_id || batch.id}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.3); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${batch.origin || 'Unknown'}${batch.variety ? ` • ${batch.variety}` : ''}</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${getStatusColor(batch.status)}20; color: ${getStatusColor(batch.status)}; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${batch.status || 'UNKNOWN'}</div>
              </div>
            `;
              }).join('');
            showButton.textContent = `Show all ${allBatches.length} batches...`;
            isExpanded = false;
          }
        });
        
        content.appendChild(showButton);
      }
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create event confirmation card
   */
  createEventConfirmCard(card, verb, accent) {
    const baseCard = this.createBaseCard(`${verb} Successfully`, accent);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Batch:</strong> ${data.batch_id || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Location:</strong> ${data.location || 'N/A'}</div>
        <div><strong>Time:</strong> ${new Date().toLocaleTimeString()}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create transformation card
   */
  createTransformationCard(card) {
    const baseCard = this.createBaseCard('Transformation Recorded');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>From:</strong> ${data.from_type || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>To:</strong> ${data.to_type || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Input:</strong> ${data.input_weight || 0} kg</div>
        <div><strong>Output:</strong> ${data.output_weight || 0} kg</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create pack/unpack card
   */
  createPackCard(card, verb) {
    const baseCard = this.createBaseCard(`${verb} Successfully`);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Packages:</strong> ${data.package_count || 0}</div>
        <div style="margin-bottom: 8px;"><strong>Total Weight:</strong> ${data.total_weight || 0} kg</div>
        <div><strong>Location:</strong> ${data.location || 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create split card
   */
  createSplitCard(card) {
    const baseCard = this.createBaseCard('Batch Split');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Original:</strong> ${data.original_batch || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>New Batches:</strong> ${data.new_batch_count || 0}</div>
        <div><strong>Weights:</strong> ${data.weights?.join(', ') || 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create knowledge search card
   */
  createKnowledgeCard(card) {
    const baseCard = this.createBaseCard('Knowledge Search');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Query:</strong> ${data.query || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Results:</strong> ${data.result_count || 0} found</div>
        <div><strong>Top Result:</strong> ${data.top_result || 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create RFQ created card
   */
  createRfqCreatedCard(card) {
    const baseCard = this.createBaseCard('RFQ Created');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>RFQ ID:</strong> ${data.rfq_id || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Product:</strong> ${data.product || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Quantity:</strong> ${data.quantity || 0} kg</div>
        <div><strong>Price:</strong> $${data.price_per_kg || 0}/kg</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create RFQ list card
   */
  createRfqListCard(card) {
    const rfqs = card.data?.rfqs || [];
    const baseCard = this.createBaseCard(`RFQs (${card.data?.count || rfqs.length})`);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto;';
    
    if (card.data && Array.isArray(card.data.rfqs)) {
      const allRfqs = card.data.rfqs;
      const visibleRfqs = allRfqs.slice(0, 4); // Match web-frontend limit
      
      // Create RFQ list content
      const rfqListContent = document.createElement('div');
      rfqListContent.className = 'rfq-list-content';
      rfqListContent.innerHTML = visibleRfqs.map(rfq => `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
          <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
            <div style="font-size: 12px; font-weight: 600; color: rgba(255, 255, 255, 0.8); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${rfq.rfq_number || rfq.rfq_id || 'N/A'}</div>
            <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${rfq.quantity_kg || 0} kg ${rfq.variety ? `• ${rfq.variety}` : ''} ${rfq.buyer ? `• ${rfq.buyer}` : ''}${rfq.offer_count ? ` • ${rfq.offer_count} offer(s)` : ''}</div>
          </div>
          <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${rfq.status || 'OPEN'}</div>
        </div>
      `).join('');
      
      content.appendChild(rfqListContent);
      
      // Add show all/less button if there are more RFQs
      if (allRfqs.length > 4) {
        const showButton = document.createElement('button');
        showButton.style.cssText = 'width: 100%; margin-top: 8px; font-size: 10px; color: rgba(16, 185, 129, 0.6); cursor: pointer; background: none; border: none; padding: 4px;';
        showButton.textContent = `Show all ${allRfqs.length} RFQs...`;
        
        let isExpanded = false;
        showButton.addEventListener('click', () => {
          if (!isExpanded) {
            // Show all RFQs
            rfqListContent.innerHTML = allRfqs.map(rfq => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-size: 12px; font-weight: 600; color: rgba(255, 255, 255, 0.8); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${rfq.rfq_number || rfq.rfq_id || 'N/A'}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${rfq.quantity_kg || 0} kg ${rfq.variety ? `• ${rfq.variety}` : ''} ${rfq.buyer ? `• ${rfq.buyer}` : ''}${rfq.offer_count ? ` • ${rfq.offer_count} offer(s)` : ''}</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${rfq.status || 'OPEN'}</div>
              </div>
            `).join('');
            showButton.textContent = 'Show less';
            isExpanded = true;
          } else {
            // Show only first 4 RFQs
            rfqListContent.innerHTML = visibleRfqs.map(rfq => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-size: 12px; font-weight: 600; color: rgba(255, 255, 255, 0.8); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${rfq.rfq_number || rfq.rfq_id || 'N/A'}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${rfq.quantity_kg || 0} kg ${rfq.variety ? `• ${rfq.variety}` : ''} ${rfq.buyer ? `• ${rfq.buyer}` : ''}${rfq.offer_count ? ` • ${rfq.offer_count} offer(s)` : ''}</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${rfq.status || 'OPEN'}</div>
              </div>
            `).join('');
            showButton.textContent = `Show all ${allRfqs.length} RFQs...`;
            isExpanded = false;
          }
        });
        
        content.appendChild(showButton);
      }
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create RFQ created card
   */
  createRfqCreatedCard(card) {
    const baseCard = this.createBaseCard('RFQ Created');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>RFQ #:</strong> ${data.rfq_number || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Quantity:</strong> ${data.quantity_kg ? `${data.quantity_kg} kg` : 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Variety:</strong> ${data.variety || 'N/A'}</div>
        <div><strong>Broadcast:</strong> ${data.broadcast_count ? `${data.broadcast_count} cooperative(s)` : 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create transformation card
   */
  createTransformationCard(card) {
    const baseCard = this.createBaseCard('Transformation');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Input Batch:</strong> ${data.input_batch_id || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Type:</strong> ${data.transformation_type || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Output Batches:</strong> ${data.output_batch_ids?.join(', ') || 'N/A'}</div>
        <div><strong>Mass Loss:</strong> ${data.mass_loss_percent != null ? `${data.mass_loss_percent}%` : 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create pack/unpack card
   */
  createPackCard(card, verb = 'Packed') {
    const baseCard = this.createBaseCard(verb);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Container:</strong> ${data.container_id || 'N/A'}</div>
        ${data.batch_ids?.length > 0 ? `
          <div style="margin-bottom: 8px;">
            <div style="font-size: 10px; opacity: 0.3; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Batches (${data.batch_ids.length})</div>
            <div style="display: flex; flex-wrap: gap; 4px;">
              ${data.batch_ids.map((id, i) => `
                <span style="display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-family: monospace; background: rgba(139, 92, 246, 0.15); color: rgba(139, 92, 246, 0.8);">
                  ${id}
                </span>
              `).join('')}
            </div>
          </div>
        ` : ''}
        ${data.container_token_id ? `<div style="margin-bottom: 8px;"><strong>Token ID:</strong> #${data.container_token_id}</div>` : ''}
        <div><strong>Status:</strong> ${verb} successfully</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create split card
   */
  createSplitCard(card) {
    const baseCard = this.createBaseCard('Split Batch');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Parent:</strong> ${data.parent_batch_id || 'N/A'}</div>
        ${data.child_batch_ids?.length > 0 ? `
          <div style="margin-bottom: 8px;">
            <div style="font-size: 10px; opacity: 0.3; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Children (${data.child_batch_ids.length})</div>
            <div style="display: flex; flex-wrap: gap; 4px;">
              ${data.child_batch_ids.map((id, i) => `
                <span style="display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-family: monospace; background: rgba(236, 72, 153, 0.15); color: rgba(236, 72, 153, 0.8);">
                  ${id}
                </span>
              `).join('')}
            </div>
          </div>
        ` : ''}
        <div><strong>Status:</strong> Split successfully</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create knowledge card
   */
  createKnowledgeCard(card) {
    const baseCard = this.createBaseCard('Knowledge');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        ${data.source_count != null ? `<div style="margin-bottom: 8px; font-size: 12px; opacity: 0.6;">${data.source_count} source(s) found</div>` : ''}
        <div style="font-size: 13px; line-height: 1.6; white-space: pre-wrap;">
          ${data.context || 'No results found.'}
        </div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create offer card
   */
  createOfferCard(card, verb, accent = '#6366F1') {
    const baseCard = this.createBaseCard(`Offer ${verb}`, accent);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Offer #:</strong> ${data.offer_number || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>RFQ #:</strong> ${data.rfq_number || 'N/A'}</div>
        ${data.acceptance_number ? `<div style="margin-bottom: 8px;"><strong>Acceptance #:</strong> ${data.acceptance_number}</div>` : ''}
        <div style="margin-bottom: 8px;"><strong>Quantity:</strong> ${data.quantity_offered_kg ? `${data.quantity_offered_kg} kg` : (data.quantity_accepted_kg ? `${data.quantity_accepted_kg} kg` : 'N/A')}</div>
        <div style="margin-bottom: 8px;"><strong>Price:</strong> ${data.price_per_kg ? `$${data.price_per_kg}/kg` : 'N/A'}</div>
        <div><strong>Cooperative:</strong> ${data.cooperative || 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create offer list card
   */
  createOfferListCard(card) {
    const offers = card.data?.offers || [];
    const baseCard = this.createBaseCard(`My Offers (${card.data?.count || offers.length})`);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto;';
    
    if (card.data && Array.isArray(card.data.offers)) {
      const allOffers = card.data.offers;
      const visibleOffers = allOffers.slice(0, 4); // Match web-frontend limit
      
      // Create offer list content
      const offerListContent = document.createElement('div');
      offerListContent.className = 'offer-list-content';
      offerListContent.innerHTML = visibleOffers.map(offer => `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
          <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
            <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.7); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${offer.offer_number}</div>
            <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${offer.rfq_number} • ${offer.quantity_offered_kg || 0} kg • $${offer.price_per_kg || 0}/kg</div>
          </div>
          <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(99, 102, 241, 0.2); color: #6366f1; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${offer.status || 'UNKNOWN'}</div>
        </div>
      `).join('');
      
      content.appendChild(offerListContent);
      
      // Add show all/less button if there are more offers
      if (allOffers.length > 4) {
        const showButton = document.createElement('button');
        showButton.style.cssText = 'width: 100%; margin-top: 8px; font-size: 10px; color: rgba(99, 102, 241, 0.6); cursor: pointer; background: none; border: none; padding: 4px;';
        showButton.textContent = `Show all ${allOffers.length} offers...`;
        
        let isExpanded = false;
        showButton.addEventListener('click', () => {
          if (!isExpanded) {
            // Show all offers
            offerListContent.innerHTML = allOffers.map(offer => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.7); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${offer.offer_number}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${offer.rfq_number} • ${offer.quantity_offered_kg || 0} kg • $${offer.price_per_kg || 0}/kg</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(99, 102, 241, 0.2); color: #6366f1; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${offer.status || 'UNKNOWN'}</div>
              </div>
            `).join('');
            showButton.textContent = 'Show less';
            isExpanded = true;
          } else {
            // Show only first 4 offers
            offerListContent.innerHTML = visibleOffers.map(offer => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.7); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${offer.offer_number}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${offer.rfq_number} • ${offer.quantity_offered_kg || 0} kg • $${offer.price_per_kg || 0}/kg</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(99, 102, 241, 0.2); color: #6366f1; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${offer.status || 'UNKNOWN'}</div>
              </div>
            `).join('');
            showButton.textContent = `Show all ${allOffers.length} offers...`;
            isExpanded = false;
          }
        });
        
        content.appendChild(showButton);
      }
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create RFQ offers card (buyer view)
   */
  createRfqOffersCard(card) {
    const offers = card.data?.offers || [];
    const baseCard = this.createBaseCard(`Offers for ${card.data?.rfq_number || 'RFQ'} (${card.data?.count || offers.length})`, '#10B981');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto;';

    // RFQ details
    if (card.data) {
      const data = card.data;
      if (data.quantity_requested_kg) {
        const field = document.createElement('div');
        field.style.cssText = 'margin-bottom: 8px;';
        field.innerHTML = `<strong>Requested:</strong> ${data.quantity_requested_kg} kg`;
        content.appendChild(field);
      }
      if (data.variety) {
        const field = document.createElement('div');
        field.style.cssText = 'margin-bottom: 8px;';
        field.innerHTML = `<strong>Variety:</strong> ${data.variety}`;
        content.appendChild(field);
      }
    }

    if (card.data && Array.isArray(card.data.offers) && card.data.offers.length > 0) {
      const divider = document.createElement('div');
      divider.style.cssText = 'margin: 12px 0; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.06);';
      divider.innerHTML = '<div style="font-size: 10px; opacity: 0.3; text-transform: uppercase; letter-spacing: 1px;">Offers</div>';
      content.appendChild(divider);
    }

    if (card.data && Array.isArray(card.data.offers)) {
      const allOffers = card.data.offers;
      const visibleOffers = allOffers.slice(0, 4);

      const offerListContent = document.createElement('div');
      offerListContent.className = 'rfq-offers-content';
      offerListContent.innerHTML = visibleOffers.map(offer => `
        <div style="padding: 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.8); font-weight: 600;">${offer.offer_number || 'N/A'}</div>
            <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981; font-weight: 500;">${offer.status || 'UNKNOWN'}</div>
          </div>
          <div style="font-size: 12px; color: rgba(255, 255, 255, 0.5); margin-bottom: 4px;">${offer.cooperative_name || 'Unknown'}</div>
          <div style="display: flex; gap: 8px; margin-top: 6px;">
            ${offer.quantity_offered_kg ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(59, 130, 246, 0.15); color: #3b82f6;">${offer.quantity_offered_kg} kg</span>` : ''}
            ${offer.price_per_kg ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(34, 197, 94, 0.15); color: #22c55e;">$${offer.price_per_kg}/kg</span>` : ''}
            ${offer.total_value_usd ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(168, 162, 158, 0.15); color: rgba(168, 162, 158, 0.8);">Total: $${offer.total_value_usd.toLocaleString()}</span>` : ''}
          </div>
          ${offer.delivery_timeline ? `<div style="font-size: 9px; color: rgba(255, 255, 255, 0.3); margin-top: 4px;">Delivery: ${offer.delivery_timeline}</div>` : ''}
        </div>
      `).join('');

      content.appendChild(offerListContent);

      if (allOffers.length > 4) {
        const showButton = document.createElement('button');
        showButton.style.cssText = 'width: 100%; margin-top: 8px; font-size: 10px; color: rgba(16, 185, 129, 0.6); cursor: pointer; background: none; border: none; padding: 4px;';
        showButton.textContent = `Show all ${allOffers.length} offers...`;

        let isExpanded = false;
        showButton.addEventListener('click', () => {
          if (!isExpanded) {
            offerListContent.innerHTML = allOffers.map(offer => `
              <div style="padding: 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                  <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.8); font-weight: 600;">${offer.offer_number || 'N/A'}</div>
                  <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981; font-weight: 500;">${offer.status || 'UNKNOWN'}</div>
                </div>
                <div style="font-size: 12px; color: rgba(255, 255, 255, 0.5); margin-bottom: 4px;">${offer.cooperative_name || 'Unknown'}</div>
                <div style="display: flex; gap: 8px; margin-top: 6px;">
                  ${offer.quantity_offered_kg ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(59, 130, 246, 0.15); color: #3b82f6;">${offer.quantity_offered_kg} kg</span>` : ''}
                  ${offer.price_per_kg ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(34, 197, 94, 0.15); color: #22c55e;">$${offer.price_per_kg}/kg</span>` : ''}
                  ${offer.total_value_usd ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(168, 162, 158, 0.15); color: rgba(168, 162, 158, 0.8);">Total: $${offer.total_value_usd.toLocaleString()}</span>` : ''}
                </div>
                ${offer.delivery_timeline ? `<div style="font-size: 9px; color: rgba(255, 255, 255, 0.3); margin-top: 4px;">Delivery: ${offer.delivery_timeline}</div>` : ''}
              </div>
            `).join('');
            showButton.textContent = 'Show less';
            isExpanded = true;
          } else {
            offerListContent.innerHTML = visibleOffers.map(offer => `
              <div style="padding: 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                  <div style="font-size: 12px; font-family: monospace; color: rgba(255, 255, 255, 0.8); font-weight: 600;">${offer.offer_number || 'N/A'}</div>
                  <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981; font-weight: 500;">${offer.status || 'UNKNOWN'}</div>
                </div>
                <div style="font-size: 12px; color: rgba(255, 255, 255, 0.5); margin-bottom: 4px;">${offer.cooperative_name || 'Unknown'}</div>
                <div style="display: flex; gap: 8px; margin-top: 6px;">
                  ${offer.quantity_offered_kg ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(59, 130, 246, 0.15); color: #3b82f6;">${offer.quantity_offered_kg} kg</span>` : ''}
                  ${offer.price_per_kg ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(34, 197, 94, 0.15); color: #22c55e;">$${offer.price_per_kg}/kg</span>` : ''}
                  ${offer.total_value_usd ? `<span style="font-size: 10px; padding: 2px 6px; border-radius: 3px; background: rgba(168, 162, 158, 0.15); color: rgba(168, 162, 158, 0.8);">Total: $${offer.total_value_usd.toLocaleString()}</span>` : ''}
                </div>
                ${offer.delivery_timeline ? `<div style="font-size: 9px; color: rgba(255, 255, 255, 0.3); margin-top: 4px;">Delivery: ${offer.delivery_timeline}</div>` : ''}
              </div>
            `).join('');
            showButton.textContent = `Show all ${allOffers.length} offers...`;
            isExpanded = false;
          }
        });

        content.appendChild(showButton);
      }
    }

    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create container list card
   */
  createContainerListCard(card) {
    const containers = card.data?.containers || [];
    const baseCard = this.createBaseCard(`Containers (${card.data?.count || containers.length})`);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto;';
    
    if (card.data && Array.isArray(card.data.containers)) {
      const allContainers = card.data.containers;
      const visibleContainers = allContainers.slice(0, 3); // Match web-frontend limit
      
      // Create container list content
      const containerListContent = document.createElement('div');
      containerListContent.className = 'container-list-content';
      containerListContent.innerHTML = visibleContainers.map(container => `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
          <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
            <div style="font-weight: 600; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${container.container_sscc || container.id || '#' + (container.container_id || 'N/A')}</div>
            <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${container.available_quantity_kg || 0}/${container.total_quantity_kg || 0} kg avail${container.price_per_kg ? ` • $${container.price_per_kg}/kg` : ''}${container.variety ? ` • ${container.variety}` : ''}</div>
          </div>
          <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(139, 92, 246, 0.2); color: #8b5cf6; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${container.status || 'AVAILABLE'}</div>
        </div>
      `).join('');
      
      content.appendChild(containerListContent);
      
      // Add show all/less button if there are more containers
      if (allContainers.length > 3) {
        const showButton = document.createElement('button');
        showButton.style.cssText = 'width: 100%; margin-top: 8px; font-size: 10px; color: rgba(139, 92, 246, 0.6); cursor: pointer; background: none; border: none; padding: 4px;';
        showButton.textContent = `Show all ${allContainers.length} containers...`;
        
        let isExpanded = false;
        showButton.addEventListener('click', () => {
          if (!isExpanded) {
            // Show all containers
            containerListContent.innerHTML = allContainers.map(container => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-weight: 600; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${container.container_sscc || container.id || '#' + (container.container_id || 'N/A')}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${container.available_quantity_kg || 0}/${container.total_quantity_kg || 0} kg avail${container.price_per_kg ? ` • $${container.price_per_kg}/kg` : ''}${container.variety ? ` • ${container.variety}` : ''}</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(139, 92, 246, 0.2); color: #8b5cf6; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${container.status || 'AVAILABLE'}</div>
              </div>
            `).join('');
            showButton.textContent = 'Show less';
            isExpanded = true;
          } else {
            // Show only first 3 containers
            containerListContent.innerHTML = visibleContainers.map(container => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); min-width: 0;">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-weight: 600; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${container.container_sscc || container.id || '#' + (container.container_id || 'N/A')}</div>
                  <div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${container.available_quantity_kg || 0}/${container.total_quantity_kg || 0} kg avail${container.price_per_kg ? ` • $${container.price_per_kg}/kg` : ''}${container.variety ? ` • ${container.variety}` : ''}</div>
                </div>
                <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(139, 92, 246, 0.2); color: #8b5cf6; font-weight: 500; margin-left: 8px; flex-shrink: 0;">${container.status || 'AVAILABLE'}</div>
              </div>
            `).join('');
            showButton.textContent = `Show all ${allContainers.length} containers...`;
            isExpanded = false;
          }
        });
        
        content.appendChild(showButton);
      }
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create purchase card
   */
  createPurchaseCard(card) {
    const baseCard = this.createBaseCard('Purchase Confirmed');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Acceptance #:</strong> ${data.acceptance_number || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Container:</strong> ${data.container_sscc || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Cooperative:</strong> ${data.cooperative || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Quantity:</strong> ${data.quantity_kg ? `${data.quantity_kg} kg` : 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Price:</strong> ${data.price_per_kg ? `$${data.price_per_kg}/kg` : 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Total:</strong> ${data.total_amount_usd ? `$${Number(data.total_amount_usd).toLocaleString()}` : 'N/A'}</div>
        <div><strong>Payment:</strong> ${data.payment_status || 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create pool list card
   */
  createPoolListCard(card) {
    const pools = card.data?.pools || [];
    const baseCard = this.createBaseCard(`Pools (${card.data?.count || pools.length})`);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto;';
    
    if (card.data && Array.isArray(card.data.pools)) {
      const allPools = card.data.pools;
      const visiblePools = allPools.slice(0, 3); // Match web-frontend limit
      
      // Create pool list content
      const poolListContent = document.createElement('div');
      poolListContent.className = 'pool-list-content';
      poolListContent.innerHTML = visiblePools.map(pool => `
        <div style="padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <div style="font-weight: 600; font-size: 12px;">${pool.destination_region || pool.container_sscc || 'Unknown'}</div>
            <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(14, 165, 233, 0.2); color: #0ea5e9; font-weight: 500;">${pool.status || 'UNKNOWN'}</div>
          </div>
          <div style="margin: 4px 0;">
            <div style="width: 100%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; overflow: hidden;">
              <div style="width: ${pool.fill_pct || 0}%; height: 100%; background: #0ea5e9; transition: width 0.3s;"></div>
            </div>
          </div>
          <div style="font-size: 12px; opacity: 0.8;">${pool.filled_kg || 0}/${pool.fill_target_kg || 0} kg • ${pool.buyer_count || 0} buyer(s) • $${pool.price_per_kg || 0}/kg</div>
        </div>
      `).join('');
      
      content.appendChild(poolListContent);
      
      // Add show all/less button if there are more pools
      if (allPools.length > 3) {
        const showButton = document.createElement('button');
        showButton.style.cssText = 'width: 100%; margin-top: 8px; font-size: 10px; color: rgba(14, 165, 233, 0.6); cursor: pointer; background: none; border: none; padding: 4px;';
        showButton.textContent = `Show all ${allPools.length} pools...`;
        
        let isExpanded = false;
        showButton.addEventListener('click', () => {
          if (!isExpanded) {
            // Show all pools
            poolListContent.innerHTML = allPools.map(pool => `
              <div style="padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <div style="font-weight: 600; font-size: 12px;">${pool.destination_region || pool.container_sscc || 'Unknown'}</div>
                  <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(14, 165, 233, 0.2); color: #0ea5e9; font-weight: 500;">${pool.status || 'UNKNOWN'}</div>
                </div>
                <div style="margin: 4px 0;">
                  <div style="width: 100%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; overflow: hidden;">
                    <div style="width: ${pool.fill_pct || 0}%; height: 100%; background: #0ea5e9; transition: width 0.3s;"></div>
                  </div>
                </div>
                <div style="font-size: 12px; opacity: 0.8;">${pool.filled_kg || 0}/${pool.fill_target_kg || 0} kg • ${pool.buyer_count || 0} buyer(s) • $${pool.price_per_kg || 0}/kg</div>
              </div>
            `).join('');
            showButton.textContent = 'Show less';
            isExpanded = true;
          } else {
            // Show only first 3 pools
            poolListContent.innerHTML = visiblePools.map(pool => `
              <div style="padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <div style="font-weight: 600; font-size: 12px;">${pool.destination_region || pool.container_sscc || 'Unknown'}</div>
                  <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(14, 165, 233, 0.2); color: #0ea5e9; font-weight: 500;">${pool.status || 'UNKNOWN'}</div>
                </div>
                <div style="margin: 4px 0;">
                  <div style="width: 100%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; overflow: hidden;">
                    <div style="width: ${pool.fill_pct || 0}%; height: 100%; background: #0ea5e9; transition: width 0.3s;"></div>
                  </div>
                </div>
                <div style="font-size: 12px; opacity: 0.8;">${pool.filled_kg || 0}/${pool.fill_target_kg || 0} kg • ${pool.buyer_count || 0} buyer(s) • $${pool.price_per_kg || 0}/kg</div>
              </div>
            `).join('');
            showButton.textContent = `Show all ${allPools.length} pools...`;
            isExpanded = false;
          }
        });
        
        content.appendChild(showButton);
      }
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create pool commitment card
   */
  createPoolCommitCard(card) {
    const baseCard = this.createBaseCard('Pool Commitment');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Commitment #:</strong> ${data.commitment_id || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Container:</strong> ${data.container_sscc || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Cooperative:</strong> ${data.cooperative || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Quantity:</strong> ${data.quantity_kg ? `${data.quantity_kg} kg` : 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Price:</strong> ${data.price_per_kg ? `$${data.price_per_kg}/kg` : 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Total:</strong> ${data.total_amount ? `$${Number(data.total_amount).toLocaleString()}` : 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Destination:</strong> ${[data.destination_region, data.destination_port].filter(Boolean).join(' → ') || 'N/A'}</div>
        ${data.pool_fill_pct != null ? `
          <div style="margin: 8px 0;">
            <div style="width: 100%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; overflow: hidden;">
              <div style="width: ${data.pool_fill_pct}%; height: 100%; background: #0ea5e9;"></div>
            </div>
            <div style="font-size: 10px; opacity: 0.6; margin-top: 2px;">Pool ${data.pool_status || ''} (${data.pool_fill_pct}%)</div>
          </div>
        ` : ''}
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create commitment list card
   */
  createCommitmentListCard(card) {
    const commitments = card.data?.commitments || [];
    const baseCard = this.createBaseCard(`My Commitments (${card.data?.count || commitments.length})`);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto;';
    
    if (card.data && Array.isArray(card.data.commitments)) {
      const allCommitments = card.data.commitments;
      const visibleCommitments = allCommitments.slice(0, 3); // Match web-frontend limit
      
      // Create commitment list content
      const commitmentListContent = document.createElement('div');
      commitmentListContent.className = 'commitment-list-content';
      commitmentListContent.innerHTML = visibleCommitments.map(commitment => `
        <div style="padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <div style="font-weight: 600; font-size: 12px; font-family: monospace;">#${commitment.commitment_id}</div>
            <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(14, 165, 233, 0.2); color: #0ea5e9; font-weight: 500;">${commitment.commitment_status || commitment.pool_status || 'UNKNOWN'}</div>
          </div>
          <div style="font-size: 12px; opacity: 0.8;">${commitment.quantity_kg || 0} kg • $${commitment.unit_price || 0}/kg → ${commitment.destination_region || 'Unknown'}</div>
        </div>
      `).join('');
      
      content.appendChild(commitmentListContent);
      
      // Add show all/less button if there are more commitments
      if (allCommitments.length > 3) {
        const showButton = document.createElement('button');
        showButton.style.cssText = 'width: 100%; margin-top: 8px; font-size: 10px; color: rgba(14, 165, 233, 0.6); cursor: pointer; background: none; border: none; padding: 4px;';
        showButton.textContent = `Show all ${allCommitments.length} commitments...`;
        
        let isExpanded = false;
        showButton.addEventListener('click', () => {
          if (!isExpanded) {
            // Show all commitments
            commitmentListContent.innerHTML = allCommitments.map(commitment => `
              <div style="padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <div style="font-weight: 600; font-size: 12px; font-family: monospace;">#${commitment.commitment_id}</div>
                  <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(14, 165, 233, 0.2); color: #0ea5e9; font-weight: 500;">${commitment.commitment_status || commitment.pool_status || 'UNKNOWN'}</div>
                </div>
                <div style="font-size: 12px; opacity: 0.8;">${commitment.quantity_kg || 0} kg • $${commitment.unit_price || 0}/kg → ${commitment.destination_region || 'Unknown'}</div>
              </div>
            `).join('');
            showButton.textContent = 'Show less';
            isExpanded = true;
          } else {
            // Show only first 3 commitments
            commitmentListContent.innerHTML = visibleCommitments.map(commitment => `
              <div style="padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <div style="font-weight: 600; font-size: 12px; font-family: monospace;">#${commitment.commitment_id}</div>
                  <div style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(14, 165, 233, 0.2); color: #0ea5e9; font-weight: 500;">${commitment.commitment_status || commitment.pool_status || 'UNKNOWN'}</div>
                </div>
                <div style="font-size: 12px; opacity: 0.8;">${commitment.quantity_kg || 0} kg • $${commitment.unit_price || 0}/kg → ${commitment.destination_region || 'Unknown'}</div>
              </div>
            `).join('');
            showButton.textContent = `Show all ${allCommitments.length} commitments...`;
            isExpanded = false;
          }
        });
        
        content.appendChild(showButton);
      }
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create EUDR compliance card
   */
  createEudrComplianceCard(card) {
    const data = card.data || {};
    const accent = data.compliant ? '#10B981' : '#EF4444';
    const baseCard = this.createBaseCard('EUDR Compliance', accent);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    const checks = data.checks || {};
    const results = data.batch_results || [];
    
    content.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
        <span style="font-size: 14px; font-weight: 600; color: ${data.compliant ? '#10b981' : '#ef4444'};">
          ${data.compliant ? '✓ Compliant' : '✗ Non-compliant'}
        </span>
        ${data.batch_count ? `<span style="font-size: 10px; opacity: 0.3;">(${data.batch_count} batch${data.batch_count > 1 ? 'es' : ''})</span>` : ''}
      </div>
      
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
        <span style="font-size: 10px; opacity: 0.3;">GPS Coordinates</span>
        <span style="font-size: 10px; color: ${checks.gps_coordinates ? '#10b981' : '#ef4444'};">${checks.gps_coordinates ? '✓' : '✗'}</span>
      </div>
      
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
        <span style="font-size: 10px; opacity: 0.3;">Photo Verified</span>
        <span style="font-size: 10px; color: ${checks.photo_verification ? '#10b981' : '#ef4444'};">${checks.photo_verification ? '✓' : '✗'}</span>
      </div>
      
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
        <span style="font-size: 10px; opacity: 0.3;">Deforestation Clear</span>
        <span style="font-size: 10px; color: ${checks.deforestation_clear ? '#10b981' : '#ef4444'};">${checks.deforestation_clear ? '✓' : '✗'}</span>
      </div>
      
      ${results.length > 0 ? `
        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.04);">
          ${results.map(r => `
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 10px; margin-bottom: 4px;">
              <span style="opacity: 0.4; font-family: monospace;">${r.batch_id}</span>
              <span style="color: ${r.compliant ? '#10b981' : '#ef4444'};">
                ${r.compliant ? '✓' : '✗'} ${r.deforestation_risk || ''}
              </span>
            </div>
          `).join('')}
        </div>
      ` : ''}
    `;
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create mass balance card
   */
  createMassBalanceCard(card) {
    const data = card.data || {};
    const accent = data.valid ? '#10B981' : '#EF4444';
    const baseCard = this.createBaseCard('Mass Balance', accent);
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    content.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
        <span style="font-size: 14px; font-weight: 600; color: ${data.valid ? '#10b981' : '#ef4444'};">
          ${data.valid ? '✓ Balanced' : '✗ Imbalanced'}
        </span>
      </div>
      <div style="margin-bottom: 8px;"><strong>Total Input:</strong> ${data.total_input_kg ? `${data.total_input_kg} kg` : 'N/A'}</div>
      <div style="margin-bottom: 8px;"><strong>Total Output:</strong> ${data.total_output_kg ? `${data.total_output_kg} kg` : 'N/A'}</div>
      <div><strong>Difference:</strong> ${data.difference_kg ? `${data.difference_kg} kg` : 'N/A'}</div>
    `;
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create DPP passport card
   */
  createDppPassportCard(card) {
    const baseCard = this.createBaseCard('Digital Product Passport');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      const p = data.product || {};
      const o = data.origin || {};
      const c = data.compliance || {};
      const bc = data.blockchain || {};
      const certs = data.certifications || [];
      
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Batch:</strong> ${p.batch_id || data.batch_id || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Grade:</strong> ${p.grade || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Weight:</strong> ${p.quantity_kg ? `${p.quantity_kg} kg` : 'N/A'}</div>
        <div style="margin-bottom: 12px;"><strong>Processing:</strong> ${p.processing || 'N/A'}</div>
        
        ${(o.region || o.country) ? `
          <div style="margin-bottom: 12px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.04);">
            <div style="font-size: 10px; opacity: 0.2; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Origin</div>
            <div style="margin-bottom: 4px;"><strong>Region:</strong> ${o.region || 'N/A'}</div>
            <div style="margin-bottom: 4px;"><strong>Country:</strong> ${o.country || 'Ethiopia'}</div>
            <div><strong>Altitude:</strong> ${o.altitude ? `${o.altitude} m` : 'N/A'}</div>
          </div>
        ` : ''}
        
        ${c.eudr_compliant !== undefined ? `
          <div style="margin-bottom: 12px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.04);">
            <div style="font-size: 10px; opacity: 0.2; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Compliance</div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 2px 0;">
              <span style="font-size: 10px; opacity: 0.3;">EUDR</span>
              <span style="font-size: 12px; font-weight: 600; color: ${c.eudr_compliant ? '#10b981' : '#ef4444'};">
                ${c.eudr_compliant ? '✓ Compliant' : '✗ Non-compliant'}
              </span>
            </div>
            ${c.deforestation_risk !== undefined ? `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 2px 0;">
                <span style="font-size: 10px; opacity: 0.3;">Deforestation Risk</span>
                <span style="font-size: 12px; font-weight: 600; color: ${
                  c.deforestation_risk === 'low' ? '#10b981' :
                  c.deforestation_risk === 'medium' ? '#f59e0b' : '#ef4444'
                }">
                  ${c.deforestation_risk || 'Unknown'}
                </span>
              </div>
            ` : ''}
          </div>
        ` : ''}
        
        ${certs.length > 0 ? `
          <div style="padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.04);">
            <div style="display: flex; flex-wrap: gap: 4px;">
              ${certs.map((cert, i) => `
                <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 9px; font-weight: 500; background: rgba(6, 182, 212, 0.15); color: rgba(6, 182, 212, 0.7);">
                  ${cert.name || cert}
                </span>
              `).join('')}
            </div>
          </div>
        ` : ''}
        
        ${bc.tx_hash ? `
          <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.04);">
            <div style="font-size: 10px; opacity: 0.2; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Blockchain</div>
            <div style="margin-bottom: 4px;"><strong>Tx Hash:</strong> ${bc.tx_hash.slice(0, 10)}…${bc.tx_hash.slice(-6)}</div>
            ${bc.network ? `<div style="margin-bottom: 4px;"><strong>Network:</strong> ${bc.network}</div>` : ''}
            ${bc.ipfs_cid ? `<div><strong>IPFS CID:</strong> ${bc.ipfs_cid.slice(0, 12)}…</div>` : ''}
          </div>
        ` : ''}
        
        ${(data.qr?.url || data.qr?.image_url) ? `
          <div style="margin-top: 12px; text-align: center;">
            <div style="font-size: 10px; color: rgba(6, 182, 212, 0.6); cursor: pointer;" onclick="window.open('${data.qr.url || data.qr.image_url}', '_blank')">
              Open full passport ↗
            </div>
          </div>
        ` : ''}
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create container DPP card
   */
  createContainerDppCard(card) {
    const baseCard = this.createBaseCard('Container DPP');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Container:</strong> ${data.container_id || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Farmers:</strong> ${data.num_farmers || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Contributors:</strong> ${data.contributors_count || 'N/A'}</div>
        <div><strong>Total Quantity:</strong> ${data.total_quantity ? `${data.total_quantity} kg` : 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create lineage card
   */
  createLineageCard(card) {
    const baseCard = this.createBaseCard('Supply Chain Lineage');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    if (card.data) {
      const data = card.data;
      content.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Product:</strong> ${data.product_id || 'N/A'}</div>
        <div style="margin-bottom: 8px;"><strong>Contributors:</strong> ${data.contributors_count || 'N/A'}</div>
        <div><strong>Total Quantity:</strong> ${data.total_quantity ? `${data.total_quantity} kg` : 'N/A'}</div>
      `;
    }
    
    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create payment card (confirm_payment, check_payment_status, etc.)
   */
  createPaymentCard(card) {
    const data = card.data || {};
    const id = data.acceptance_number || (data.commitment_id ? `Commitment #${data.commitment_id}` : null);
    const status = data.payment_status || data.status;
    const statusColor =
      status === 'PAID' || status === 'COMPLETED' ? '#10b981' :
      status === 'PENDING' || status === 'AWAITING_PAYMENT' ? '#f59e0b' : 'rgba(255,255,255,0.6)';

    const baseCard = this.createBaseCard('Payment', '#10B981');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';

    content.innerHTML = `
      ${id ? `<div style="margin-bottom: 8px;"><strong>Reference:</strong> <span style="font-family: monospace;">${id}</span></div>` : ''}
      ${data.cooperative ? `<div style="margin-bottom: 8px;"><strong>Cooperative:</strong> ${data.cooperative}</div>` : ''}
      ${data.quantity_kg ? `<div style="margin-bottom: 8px;"><strong>Quantity:</strong> ${Number(data.quantity_kg).toLocaleString()} kg</div>` : ''}
      ${(data.total_amount || data.amount) ? `<div style="margin-bottom: 8px;"><strong>Amount:</strong> $${Number(data.total_amount || data.amount).toLocaleString()}</div>` : ''}
      ${status ? `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0; margin-bottom: 4px;">
          <span style="font-size: 10px; opacity: 0.3; text-transform: uppercase; letter-spacing: 1px;">Status</span>
          <span style="font-size: 12px; font-weight: 600; color: ${statusColor};">${status}</span>
        </div>
      ` : ''}
      ${data.buyer_confirmed !== undefined ? `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 2px 0;">
          <span style="font-size: 10px; opacity: 0.3;">Buyer Confirmed</span>
          <span style="font-size: 11px; color: ${data.buyer_confirmed ? '#10b981' : 'rgba(255,255,255,0.3)'};">${data.buyer_confirmed ? '✓' : '○'}</span>
        </div>
      ` : ''}
      ${data.coop_confirmed !== undefined ? `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 2px 0;">
          <span style="font-size: 10px; opacity: 0.3;">Coop Confirmed</span>
          <span style="font-size: 11px; color: ${data.coop_confirmed ? '#10b981' : 'rgba(255,255,255,0.3)'};">${data.coop_confirmed ? '✓' : '○'}</span>
        </div>
      ` : ''}
      ${data.delivery_status ? `<div style="margin-top: 6px;"><strong>Delivery:</strong> ${data.delivery_status}</div>` : ''}
      ${data.settlement_tx ? `<div style="margin-top: 6px; font-size: 11px; font-family: monospace; opacity: 0.5;">Tx: ${data.settlement_tx.slice(0, 12)}…</div>` : ''}
    `;

    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create dispute payment card
   */
  createDisputePaymentCard(card) {
    const data = card.data || {};
    const baseCard = this.createBaseCard('Payment Dispute', '#F59E0B');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';

    content.innerHTML = `
      ${data.acceptance_number ? `<div style="margin-bottom: 8px;"><strong>Acceptance #:</strong> <span style="font-family: monospace;">${data.acceptance_number}</span></div>` : ''}
      ${data.dispute_reason ? `
        <div style="margin-bottom: 10px;">
          <div style="font-size: 10px; opacity: 0.3; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Reason</div>
          <div style="font-size: 12px; color: rgba(245, 158, 11, 0.85); line-height: 1.5;">${data.dispute_reason}</div>
        </div>
      ` : ''}
      ${data.has_receipt !== undefined || data.has_settlement !== undefined || data.buyer_confirmed !== undefined ? `
        <div style="margin-bottom: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.04);">
          <div style="font-size: 10px; opacity: 0.2; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">Evidence on Record</div>
          ${data.has_receipt !== undefined ? `
            <div style="display: flex; justify-content: space-between; padding: 2px 0;">
              <span style="font-size: 10px; opacity: 0.4;">Receipt photo</span>
              <span style="font-size: 11px; color: ${data.has_receipt ? '#10b981' : 'rgba(255,255,255,0.2)'};">${data.has_receipt ? '✓' : '○'}</span>
            </div>
          ` : ''}
          ${data.has_settlement !== undefined ? `
            <div style="display: flex; justify-content: space-between; padding: 2px 0;">
              <span style="font-size: 10px; opacity: 0.4;">Blockchain settlement</span>
              <span style="font-size: 11px; color: ${data.has_settlement ? '#10b981' : 'rgba(255,255,255,0.2)'};">${data.has_settlement ? '✓' : '○'}</span>
            </div>
          ` : ''}
          ${data.buyer_confirmed !== undefined ? `
            <div style="display: flex; justify-content: space-between; padding: 2px 0;">
              <span style="font-size: 10px; opacity: 0.4;">Buyer confirmed</span>
              <span style="font-size: 11px; color: ${data.buyer_confirmed ? '#10b981' : 'rgba(255,255,255,0.2)'};">${data.buyer_confirmed ? '✓' : '○'}</span>
            </div>
          ` : ''}
        </div>
      ` : ''}
      <div style="padding: 8px 10px; border-radius: 8px; background: rgba(245, 158, 11, 0.06); font-size: 11px; color: rgba(245, 158, 11, 0.7);">
        An administrator will review and contact both parties.
      </div>
    `;

    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create shipment confirm card (cooperative confirms shipped)
   */
  createShipmentConfirmCard(card) {
    const data = card.data || {};
    const baseCard = this.createBaseCard('Shipment Confirmed', '#6366F1');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';

    content.innerHTML = `
      ${data.acceptance_number ? `<div style="margin-bottom: 8px;"><strong>Acceptance #:</strong> <span style="font-family: monospace;">${data.acceptance_number}</span></div>` : ''}
      ${data.quantity_kg ? `<div style="margin-bottom: 8px;"><strong>Quantity:</strong> ${Number(data.quantity_kg).toLocaleString()} kg</div>` : ''}
      ${data.delivery_location ? `<div style="margin-bottom: 8px;"><strong>Destination:</strong> ${data.delivery_location}</div>` : ''}
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0; margin-bottom: 8px;">
        <span style="font-size: 10px; opacity: 0.3; text-transform: uppercase; letter-spacing: 1px;">Delivery Status</span>
        <span style="font-size: 12px; font-weight: 600; color: #6366f1;">SHIPPED →</span>
      </div>
      <div style="padding: 8px 10px; border-radius: 8px; background: rgba(99, 102, 241, 0.06); font-size: 11px; color: rgba(99, 102, 241, 0.7);">
        Buyer has been notified. Awaiting delivery confirmation.
      </div>
    `;

    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create delivery confirm card (buyer confirms delivered)
   */
  createDeliveryConfirmCard(card) {
    const data = card.data || {};
    const baseCard = this.createBaseCard('Delivery Confirmed', '#10B981');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';

    const deliveredAt = data.delivered_at
      ? data.delivered_at.slice(0, 19).replace('T', ' ')
      : null;

    content.innerHTML = `
      ${data.acceptance_number ? `<div style="margin-bottom: 8px;"><strong>Acceptance #:</strong> <span style="font-family: monospace;">${data.acceptance_number}</span></div>` : ''}
      ${deliveredAt ? `<div style="margin-bottom: 8px;"><strong>Delivered At:</strong> ${deliveredAt}</div>` : ''}
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0; margin-bottom: 8px;">
        <span style="font-size: 10px; opacity: 0.3; text-transform: uppercase; letter-spacing: 1px;">Delivery Status</span>
        <span style="font-size: 12px; font-weight: 600; color: #10b981;">✓ DELIVERED</span>
      </div>
      <div style="padding: 8px 10px; border-radius: 8px; background: rgba(16, 185, 129, 0.06); font-size: 11px; color: rgba(16, 185, 129, 0.7);">
        Cooperative notified. Transaction complete! 🎉
      </div>
    `;

    baseCard.appendChild(content);
    return baseCard;
  }

  /**
   * Create generic card for unknown types
   */
  createGenericCard(card) {
    const baseCard = this.createBaseCard('Action Completed');
    const content = document.createElement('div');
    content.style.cssText = 'color: rgba(255, 255, 255, 0.7); font-size: 13px; line-height: 1.5;';
    
    content.innerHTML = `
      <div style="margin-bottom: 8px;"><strong>Type:</strong> ${card.type}</div>
      <div><strong>Status:</strong> Completed successfully</div>
    `;
    
    baseCard.appendChild(content);
    return baseCard;
  }
}

// Export for use in miniapps
window.ActionCards = ActionCards;
