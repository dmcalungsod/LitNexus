export namespace domain {
	
	export class DownloadResult {
	    doi: string;
	    status: string;
	    source?: string;
	    filename?: string;
	    error?: string;
	
	    static createFrom(source: any = {}) {
	        return new DownloadResult(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.doi = source["doi"];
	        this.status = source["status"];
	        this.source = source["source"];
	        this.filename = source["filename"];
	        this.error = source["error"];
	    }
	}
	export class Paper {
	    doi: string;
	    title: string;
	    authors: string;
	    year: number;
	    abstract?: string;
	    generation: number;
	    pdf_status: string;
	    pdf_status_reason?: string;
	    local_filepath?: string;
	    external_reference_count: number;
	    external_citation_count: number;
	    external_counts_source?: string;
	    external_counts_fetched_at?: string;
	    references_fetch_status?: string;
	    citations_fetch_status?: string;
	
	    static createFrom(source: any = {}) {
	        return new Paper(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.doi = source["doi"];
	        this.title = source["title"];
	        this.authors = source["authors"];
	        this.year = source["year"];
	        this.abstract = source["abstract"];
	        this.generation = source["generation"];
	        this.pdf_status = source["pdf_status"];
	        this.pdf_status_reason = source["pdf_status_reason"];
	        this.local_filepath = source["local_filepath"];
	        this.external_reference_count = source["external_reference_count"];
	        this.external_citation_count = source["external_citation_count"];
	        this.external_counts_source = source["external_counts_source"];
	        this.external_counts_fetched_at = source["external_counts_fetched_at"];
	        this.references_fetch_status = source["references_fetch_status"];
	        this.citations_fetch_status = source["citations_fetch_status"];
	    }
	}

}

export namespace settings {
	
	export class AppSettings {
	    unpaywall_email: string;
	    institutional_proxy: string;
	    output_directory: string;
	    verify_ssl: boolean;
	    ui_mode: string;
	
	    static createFrom(source: any = {}) {
	        return new AppSettings(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.unpaywall_email = source["unpaywall_email"];
	        this.institutional_proxy = source["institutional_proxy"];
	        this.output_directory = source["output_directory"];
	        this.verify_ssl = source["verify_ssl"];
	        this.ui_mode = source["ui_mode"];
	    }
	}

}

